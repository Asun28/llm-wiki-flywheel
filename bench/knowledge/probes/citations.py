"""Probe `citations`: STUB for the RED commit of card T1-KBEVAL-CITATIONS.

Keeps the entry `run(ctx)` and the loader names and returns a well-formed but
wrong result: the arm is measured with zero cases and no metrics, and no `kb`
function is called. The GREEN commit replaces this file with the real probe.
"""

from __future__ import annotations

from pathlib import Path


def load_pages(path: Path) -> dict[str, dict]:
    return {}


def load_questions(path: Path, pages: dict[str, dict]) -> list[dict]:
    return []


def run(ctx) -> dict:
    return {
        "invariants": [],
        "arms": {"scripted": {"status": "measured", "cases": 0, "metrics": {}}},
    }
