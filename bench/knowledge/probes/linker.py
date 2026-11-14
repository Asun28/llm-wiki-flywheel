"""Probe `linker`: RED stub. Returns a well-formed but empty arm and calls no kb function."""

from __future__ import annotations


def run(ctx) -> dict:
    return {"invariants": [], "arms": {"inject": {"status": "measured", "cases": 0, "metrics": {}}}}
