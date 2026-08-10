"""Requirement retrieval through Parallel.

Two things happen here that do not happen in a normal search wrapper.

**Trust tiers are assigned outside the model.** A source's tier is decided by
its URL against the destination's known official domain — a deterministic check
the model cannot influence. This is what stops a well-written blog post from
becoming a mandatory delivery requirement.

**Retrieved text is hashed.** The same URL fetched later with a different hash
means the destination changed its requirements, which is the difference between
a spec you retrieved once and a spec you can trust today.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

logger = logging.getLogger("preflight.parallel")

PARALLEL_SEARCH_URL = "https://api.parallel.ai/v1beta/search"

#: Hosts that publish standards a destination may explicitly reference.
#: These reach Tier C only — a referenced standard binds only for the clauses
#: the destination actually cites.
STANDARDS_HOSTS = {
    "itu.int", "smpte.org", "ebu.ch", "iso.org", "w3.org", "tech.ebu.ch",
}


class RetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetrievedSource:
    url: str
    title: str
    excerpts: list[str]
    retrieved_at: str
    source_hash: str
    trust_tier: str
    host: str

    @property
    def text(self) -> str:
        return "\n\n".join(self.excerpts)

    @property
    def may_create_mandatory_rule(self) -> bool:
        return self.trust_tier in ("A", "B", "C")


def classify_tier(url: str, official_domains: set[str]) -> str:
    """Assign a trust tier from the URL alone.

    Deterministic and model-independent by design. A source is Tier A only if
    it is served by the destination's own documented domain.
    """
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if not host:
        return "D"

    for domain in official_domains:
        domain = domain.lower().removeprefix("www.")
        if host == domain or host.endswith("." + domain):
            return "A"

    for standard in STANDARDS_HOSTS:
        if host == standard or host.endswith("." + standard):
            return "C"

    return "D"


def _post(url: str, payload: dict, api_key: str, timeout: int = 180) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", "replace")
        raise RetrievalError(f"Parallel returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RetrievalError(f"could not reach Parallel: {exc.reason}") from exc


def search_destination_requirements(
    *,
    api_key: str,
    destination_name: str,
    official_domains: set[str],
    extra_queries: list[str] | None = None,
    max_results: int = 8,
) -> list[RetrievedSource]:
    """Retrieve candidate requirement sources for one destination.

    Queries are scoped to the named destination. Preflight does not perform
    open-ended research about delivery in general — a requirement that is not
    published by the destination is not that destination's requirement.
    """
    if not api_key:
        raise RetrievalError("Parallel is not configured")

    queries = [
        f"{destination_name} technical delivery requirements specification",
        f"{destination_name} video format resolution codec audio requirements",
    ]
    if extra_queries:
        queries.extend(extra_queries)

    payload = {
        "objective": (
            f"Find the official published technical delivery requirements for "
            f"{destination_name}: accepted container, video codec, resolution, "
            f"frame rate, bitrate, audio codec, sample rate, loudness, and "
            f"subtitle format."
        ),
        "search_queries": queries[:5],
        "processor": "base",
        "max_results": max_results,
        "max_chars_per_result": 6000,
    }

    data = _post(PARALLEL_SEARCH_URL, payload, api_key)
    now = datetime.now(UTC).isoformat(timespec="seconds")

    sources: list[RetrievedSource] = []
    for result in data.get("results", []):
        url = result.get("url") or ""
        if not url:
            continue
        excerpts = [e for e in (result.get("excerpts") or []) if e and e.strip()]
        if not excerpts:
            continue

        joined = "\n\n".join(excerpts)
        sources.append(
            RetrievedSource(
                url=url,
                title=(result.get("title") or "").strip()[:300],
                excerpts=excerpts,
                retrieved_at=now,
                source_hash=hashlib.sha256(joined.encode()).hexdigest(),
                trust_tier=classify_tier(url, official_domains),
                host=(urlparse(url).hostname or "").lower(),
            )
        )

    tiers = {}
    for source in sources:
        tiers[source.trust_tier] = tiers.get(source.trust_tier, 0) + 1
    logger.info("retrieved %d sources for %s: %s", len(sources), destination_name, tiers)

    return sources


def detect_drift(
    previous: dict[str, str], current: list[RetrievedSource]
) -> list[dict[str, str]]:
    """Compare source hashes across retrievals.

    A changed hash on a Tier A URL is the signal that a destination has revised
    its requirements. Historical passports keep the version they were issued
    against; only new preflight runs adopt the change.
    """
    changes: list[dict[str, str]] = []
    for source in current:
        was = previous.get(source.url)
        if was is None:
            changes.append({"url": source.url, "change": "new", "hash": source.source_hash})
        elif was != source.source_hash:
            changes.append({
                "url": source.url,
                "change": "modified",
                "previousHash": was,
                "hash": source.source_hash,
            })

    seen = {s.url for s in current}
    for url in previous:
        if url not in seen:
            changes.append({"url": url, "change": "unreachable"})
    return changes


#: Instruction-shaped text that has no business appearing inside a technical
#: specification. Presence is logged and the text is neutralised before it
#: reaches the model — see wrap_untrusted().
_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)\s+instructions"
    r"|disregard\s+(the\s+)?(above|previous|system)"
    r"|you\s+are\s+now\s+"
    r"|new\s+instructions?\s*:"
    r"|system\s*prompt"
    r"|mark\s+(all\s+)?(rules?|requirements?)\s+as\s+(optional|satisfied|passed)"
    r"|treat\s+this\s+as\s+(verified|compliant))",
    re.IGNORECASE,
)


def looks_like_injection(text: str) -> list[str]:
    return [m.group(0) for m in _INJECTION_PATTERNS.finditer(text)]
