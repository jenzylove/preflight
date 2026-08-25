"""Prove the central thesis on real published data.

If two real destinations never actually conflict, Preflight is a linter and the
product is not worth building. This script answers that question with the two
Gate 0 rule packs before anything else is written.
"""

from __future__ import annotations

import sys as _sys

# Windows consoles default to cp1252. A report that crashes while
# printing a citation is worse than no report.
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "contracts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from preflight_contracts.compare import find_conflicts  # noqa: E402
from seed_rule_packs import ARTDOCFEST, BERLINALE  # noqa: E402


def main() -> int:
    packs = [BERLINALE, ARTDOCFEST]
    conflicts = find_conflicts(packs)

    print(f"destinations: {', '.join(p.destination_id for p in packs)}")
    print(f"required rules: {sum(len(p.required_rules()) for p in packs)}")
    print(f"irreconcilable conflicts found: {len(conflicts)}\n")

    evidence = {eid: ev for p in packs for eid, ev in p.evidence.items()}

    for conflict in conflicts:
        dest_a, dest_b = conflict["destinations"]
        req_a, req_b = conflict["requirements"]
        ev_a, ev_b = conflict["evidence"]
        sev_a, sev_b = conflict["severities"]
        print(f"  [{conflict['strength'].upper()}] {conflict['assetType']}.{conflict['field']}")
        print(f"    {dest_a:12} {sev_a:11} {req_a}")
        print(f"      |- {evidence[ev_a].url}")
        print(f'         "{evidence[ev_a].quoted_excerpt[:100]}..."')
        print(f"    {dest_b:12} {sev_b:11} {req_b}")
        print(f"      |- {evidence[ev_b].url}")
        print(f'         "{evidence[ev_b].quoted_excerpt[:100]}..."')
        print(f"    resolution: {conflict['resolution']}\n")

    if not conflicts:
        print("NO CONFLICT FOUND - the multi-destination premise is unproven.")
        return 1

    print("Thesis holds: one master cannot satisfy both destinations, and "
          "Preflight can cite each destination's own words for why.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
