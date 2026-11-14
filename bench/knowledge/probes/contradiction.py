"""Stub of probe `contradiction`, committed only to record a behavioural RED.

It keeps the `run(ctx)` entry and returns a well-formed result with every metric
at zero. It reads no case set and calls neither kb function.
"""

from __future__ import annotations

CATEGORIES = (
    "negation",
    "both-negated",
    "date",
    "number",
    "paraphrase",
    "negated-paraphrase",
    "unrelated-negation",
)


def zero_arm() -> dict:
    metrics = dict.fromkeys(("tp", "fp", "fn", "tn", "precision", "recall"), 0)
    for category in CATEGORIES:
        metrics[f"rows_{category}"] = 0
        metrics[f"flagged_{category}"] = 0
    return {"status": "measured", "cases": 0, "metrics": metrics}


def run(ctx) -> dict:
    return {"invariants": ["I10"], "arms": {"detect": zero_arm(), "signal": zero_arm()}}
