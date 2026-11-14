"""Probe `trace`: stub for the RED commit of card T1-KBEVAL-TRACE.

Returns a well-formed but wrong result: zero counts, no sentences, an empty sample
file, and no invariant. It reads no wiki, raw or template file and calls no `kb`
function. The real probe replaces it in the GREEN commit.
"""

from __future__ import annotations

from pathlib import Path

METRICS = (
    "pages_unparsed",
    "pages_no_source_field",
    "pages_no_text_source",
    "refs_text",
    "refs_undecodable",
    "refs_non_text",
    "refs_missing",
    "refs_url",
    "refs_outside",
    "refs_total",
    "sentences",
    "sentences_short",
    "sentences_no_text_source",
    "band_high",
    "band_mid",
    "band_low",
    "sample_pages",
    "sample_sentences",
)


def page_sentences(text: str) -> list[dict]:
    return []


def containment(sentence: str, source_texts: list[str]) -> float | None:
    return None


def run(ctx) -> dict:
    out = Path(ctx.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "trace-sample.jsonl").write_bytes(b"")
    return {
        "invariants": [],
        "arms": {
            "containment": {"status": "measured", "cases": 0, "metrics": dict.fromkeys(METRICS, 0)},
            "templates": {
                "status": "measured",
                "cases": 0,
                "metrics": {"templates_total": 0, "templates_with_claim_span": 0},
            },
        },
    }
