"""Probe `contradiction`: precision and recall of the keyword contradiction check.

Arms:
- `detect`: `kb.ingest.contradiction.detect_contradictions([claim], [page])` per row,
  flagged when the returned list is not empty (includes the token-overlap gate).
- `signal`: `kb.ingest.contradiction._has_contradiction_signal(claim, existing)` per
  row, flagged when it returns true (the negation-word check alone).

Positive is the label `contradiction`. Case set: `ctx.data / "cases.jsonl"`.
"""

from __future__ import annotations

import json
from pathlib import Path

CATEGORY_LABEL = {
    "negation": "contradiction",
    "both-negated": "contradiction",
    "date": "contradiction",
    "number": "contradiction",
    "paraphrase": "consistent",
    "negated-paraphrase": "consistent",
    "unrelated-negation": "consistent",
}
FIELDS = ("id", "category", "claim", "existing", "label", "why")
POSITIVE = "contradiction"


def load_cases(path: Path) -> list[dict]:
    """Read and check the case set; raise ValueError naming the file and line on a bad line."""
    rows: list[dict] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):

            def bad(cause: str, number: int = number) -> ValueError:
                return ValueError(f"{path} line {number}: {cause}")

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise bad(f"not JSON ({exc.msg})") from None
            if not isinstance(row, dict):
                raise bad("not a JSON object")
            for field in FIELDS:
                if field not in row:
                    raise bad(f"missing field {field!r}")
                if not isinstance(row[field], str):
                    raise bad(f"field {field!r} is not a string")
            if row["id"] in seen:
                raise bad(f"repeated id {row['id']!r}")
            if row["category"] not in CATEGORY_LABEL:
                raise bad(f"unknown category {row['category']!r}")
            if row["label"] != CATEGORY_LABEL[row["category"]]:
                raise bad(
                    f"label {row['label']!r} is not {CATEGORY_LABEL[row['category']]!r} "
                    f"for category {row['category']!r}"
                )
            seen.add(row["id"])
            rows.append(row)
    return rows


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0


def measure(rows: list[dict], flags: list[bool]) -> dict:
    """Return the arm for rows and whether each row was flagged."""
    metrics = {}
    for category in CATEGORY_LABEL:
        metrics[f"rows_{category}"] = 0
        metrics[f"flagged_{category}"] = 0
    tp = fp = fn = tn = 0
    for row, flagged in zip(rows, flags, strict=True):
        positive = row["label"] == POSITIVE
        metrics[f"rows_{row['category']}"] += 1
        metrics[f"flagged_{row['category']}"] += int(flagged)
        if positive and flagged:
            tp += 1
        elif positive:
            fn += 1
        elif flagged:
            fp += 1
        else:
            tn += 1
    metrics.update(
        tp=tp, fp=fp, fn=fn, tn=tn, precision=ratio(tp, tp + fp), recall=ratio(tp, tp + fn)
    )
    return {"status": "measured", "cases": len(rows), "metrics": metrics}


def run(ctx) -> dict:
    # Looked up at call time so a test can replace either function on the module.
    from kb.ingest import contradiction

    rows = load_cases(Path(ctx.data) / "cases.jsonl")
    detect = [
        bool(
            contradiction.detect_contradictions(
                [row["claim"]], [{"id": row["id"], "content": row["existing"]}]
            )
        )
        for row in rows
    ]
    signal = [
        bool(contradiction._has_contradiction_signal(row["claim"], row["existing"])) for row in rows
    ]
    return {
        "invariants": ["I10"],
        "arms": {"detect": measure(rows, detect), "signal": measure(rows, signal)},
    }
