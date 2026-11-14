"""Probe `rebuild`: placeholder that keeps the probe entry and measures nothing yet.

Spec: specs/kb-baseline.md (R8); card specs/tasks/T1-KBEVAL-REBUILD.md.
"""

from __future__ import annotations


def run(ctx) -> dict:
    empty = {"status": "measured", "cases": 0, "metrics": {}}
    return {
        "invariants": [],
        "arms": {"idempotence": dict(empty), "order": dict(empty), "scan": dict(empty)},
    }
