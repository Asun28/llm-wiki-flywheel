"""Probe `provenance`: stub for the RED commit of card T1-KBEVAL-PROVENANCE.

It keeps `run(ctx)` and returns a well-formed result with every arm measured,
zero cases and no metrics. It calls no `kb` function and reads nothing.
"""

from __future__ import annotations


def run(ctx) -> dict:
    empty = {"status": "measured", "cases": 0, "metrics": {}}
    return {
        "invariants": [],
        "arms": {"trust": dict(empty), "refine": dict(empty), "captures": dict(empty)},
    }
