"""Probe `retrieval`: stub that records the behavioural RED of card T1-KBEVAL-RETRIEVAL.

It keeps the `run(ctx)` entry and returns a well-formed record with every arm
`measured`, zero cases and no metrics. It reads no data file, writes no wiki and
calls neither `search_pages` nor `tokenize`. The next commit replaces it with
the full probe.
"""

from __future__ import annotations


def run(ctx) -> dict:
    empty = {"status": "measured", "cases": 0, "metrics": {}}
    return {
        "invariants": ["I8"],
        "arms": {"bm25": dict(empty), "tokenize": dict(empty), "hybrid": dict(empty)},
    }
