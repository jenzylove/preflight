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


PARALLEL_EXTRACT_URL = "https://api.parallel.ai/v1beta/extract"


def fetch_full_sources(
    *, api_key: str, sources: list[RetrievedSource], max_urls: int = 10
) -> list[RetrievedSource]:
    """Replace search snippets with the full text of each page.

    Search finds the right page; it does not read it. A snippet is chosen for
    relevance to a query, not for completeness, so a specification table can be
    entirely absent from results that correctly identify the page containing it.
    Extracting the page is what turns "we found the spec" into "we read it".

    Sources that cannot be extracted keep their excerpts rather than being
    dropped — partial evidence with a citation is still better than none, and
    the rule schema will reject anything that cannot be quoted.
    """
    if not sources:
        return []
    if not api_key:
        raise RetrievalError("Parallel is not configured")

    wanted = [s for s in sources if s.may_create_mandatory_rule][:max_urls]
    if not wanted:
        return sources

    try:
        data = _post(
            PARALLEL_EXTRACT_URL,
            {"urls": [s.url for s in wanted], "full_content": True},
            api_key,
            timeout=300,
        )
    except RetrievalError as exc:
        logger.warning("extraction unavailable, continuing on snippets: %s", exc)
        return sources

    full_by_url: dict[str, str] = {}
    for result in data.get("results", []):
        content = (result.get("full_content") or "").strip()
        if content:
            full_by_url[result.get("url", "")] = content

    for error in data.get("errors") or []:
        logger.info("could not extract %s", (error or {}).get("url", "?"))

    upgraded: list[RetrievedSource] = []
    for source in sources:
        content = full_by_url.get(source.url)
        if not content or len(content) <= len(source.text):
            upgraded.append(source)
            continue
        # The hash follows the text it describes, so drift detection compares
        # like with like across runs.
        upgraded.append(
            RetrievedSource(
                url=source.url,
                title=source.title,
                excerpts=[content],
                retrieved_at=source.retrieved_at,
                source_hash=hashlib.sha256(content.encode()).hexdigest(),
                trust_tier=source.trust_tier,
                host=source.host,
            )
        )

    gained = sum(
        1 for a, b in zip(sources, upgraded, strict=False) if a.source_hash != b.source_hash
    )
    logger.info("extracted full content for %d of %d sources", gained, len(sources))
    return upgraded


def machine_readability(source: RetrievedSource) -> float:
    """How much of a specification this text plausibly contains.

    Used to warn when an official page yields almost nothing measurable — the
    page exists and is authoritative, but its requirements are in an image, a
    PDF, or rendered by script. That is a fact about the destination worth
    surfacing rather than a silent extraction failure.
    """
    terms = (
        "mbps", "kbps", "lufs", "fps", "frame rate", "resolution", "codec",
        "bitrate", "bit rate", "khz", "aspect", "subtitle", "1920", "resolution",
    )
    lowered = source.text.lower()
    return sum(1 for t in set(terms) if t in lowered) / len(set(terms))
