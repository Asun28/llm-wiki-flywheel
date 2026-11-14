"""Acceptance tests 1-4 of card T1-KBEVAL-CONTRADICTION for the `contradiction` probe."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import REPO

PROBES = REPO / "bench" / "knowledge" / "probes"
PROBE = PROBES / "contradiction.py"
CASES = REPO / "bench" / "knowledge" / "data" / "contradiction" / "cases.jsonl"

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


@pytest.fixture
def probe():
    """The probe module loaded in-process from its file, as the runner loads it."""
    name = "kbeval_probe_contradiction_under_test"
    spec = importlib.util.spec_from_file_location(name, PROBE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(name, None)


def row(rid: str, category: str, claim: str = "c", existing: str = "e", **override) -> dict:
    data = {
        "id": rid,
        "category": category,
        "claim": claim,
        "existing": existing,
        "label": CATEGORY_LABEL[category],
        "why": "fixture row",
    }
    data.update(override)
    return data


def ctx_with(tmp_path: Path, lines: list[str]) -> SimpleNamespace:
    data = tmp_path / "data"
    data.mkdir()
    (data / "cases.jsonl").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return SimpleNamespace(tmp=tmp_path, data=data, wiki=tmp_path, raw=tmp_path, out=tmp_path)


def ctx_with_rows(tmp_path: Path, rows: list[dict]) -> SimpleNamespace:
    return ctx_with(tmp_path, [json.dumps(r) for r in rows])


# -- acceptance 1: the committed case set [R1] [R2] -------------------------------


def test_committed_case_set_has_six_fields_unique_ids_and_ten_rows_per_category():
    lines = CASES.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]

    assert all(isinstance(r, dict) and set(r) == set(FIELDS) for r in rows)
    assert all(isinstance(r[f], str) and r[f].strip() for r in rows for f in FIELDS)
    assert len({r["id"] for r in rows}) == len(rows)
    assert all(r["label"] == CATEGORY_LABEL[r["category"]] for r in rows)
    for category in CATEGORY_LABEL:
        assert sum(r["category"] == category for r in rows) >= 10, category


def test_committed_case_set_loads_through_the_probe_without_error(probe, monkeypatch):
    monkeypatch.setattr("kb.ingest.contradiction.detect_contradictions", lambda c, p: [])
    monkeypatch.setattr("kb.ingest.contradiction._has_contradiction_signal", lambda c, e: False)
    ctx = SimpleNamespace(data=CASES.parent)

    result = probe.run(ctx)

    assert result["arms"]["detect"]["cases"] == len(CASES.read_text("utf-8").splitlines())


# -- acceptance 2: one ValueError per malformed-line cause [R2] -----------------


def assert_rejected(probe, ctx, line_number: int) -> None:
    with pytest.raises(ValueError) as caught:
        probe.run(ctx)
    message = str(caught.value)
    assert "cases.jsonl" in message
    assert f"line {line_number}" in message


def test_line_that_is_not_a_json_object_is_rejected_with_file_and_line(probe, tmp_path):
    ctx = ctx_with(tmp_path, [json.dumps(row("a", "negation")), '["a", "list"]'])
    assert_rejected(probe, ctx, 2)


def test_line_that_is_not_json_at_all_is_rejected_with_file_and_line(probe, tmp_path):
    ctx = ctx_with(tmp_path, ["{not json"])
    assert_rejected(probe, ctx, 1)


def test_blank_line_is_rejected_with_file_and_line(probe, tmp_path):
    ctx = ctx_with(tmp_path, [json.dumps(row("a", "negation")), "", json.dumps(row("b", "date"))])
    assert_rejected(probe, ctx, 2)


def test_row_missing_a_field_is_rejected_with_file_and_line(probe, tmp_path):
    incomplete = row("b", "date")
    del incomplete["why"]
    ctx = ctx_with_rows(tmp_path, [row("a", "negation"), row("c", "number"), incomplete])
    assert_rejected(probe, ctx, 3)


def test_field_that_is_not_a_string_is_rejected_with_file_and_line(probe, tmp_path):
    ctx = ctx_with_rows(tmp_path, [row("a", "negation", claim=["not", "a", "string"])])
    assert_rejected(probe, ctx, 1)


def test_repeated_id_is_rejected_with_file_and_line(probe, tmp_path):
    ctx = ctx_with_rows(tmp_path, [row("a", "negation"), row("b", "date"), row("a", "number")])
    assert_rejected(probe, ctx, 3)


def test_unknown_category_is_rejected_with_file_and_line(probe, tmp_path):
    bad = {**row("b", "date"), "category": "sarcasm"}
    ctx = ctx_with_rows(tmp_path, [row("a", "negation"), bad])
    assert_rejected(probe, ctx, 2)


def test_label_that_is_not_the_categorys_label_is_rejected_with_file_and_line(probe, tmp_path):
    bad = row("b", "paraphrase", label="contradiction")
    ctx = ctx_with_rows(tmp_path, [row("a", "negation"), bad])
    assert_rejected(probe, ctx, 2)


# -- acceptance 3: hand-computed metrics with stubbed kb functions [R3] [R4] [R5] --

FOUR_ROWS = [
    row("r1", "negation", claim="claim one", existing="existing one"),
    row("r2", "date", claim="claim two", existing="existing two"),
    row("r3", "paraphrase", claim="claim three", existing="existing three"),
    row("r4", "unrelated-negation", claim="claim four", existing="existing four"),
]
# Each stub answers true only for the exact argument shape R3 / R4 name, so a probe
# that calls with another shape gets a different count.
DETECT_FLAGS = {
    (("claim one",), "r1", "existing one"),
    (("claim three",), "r3", "existing three"),
}
SIGNAL_FLAGS = {
    ("claim one", "existing one"),
    ("claim two", "existing two"),
    ("claim four", "existing four"),
}


def stub_detect(flags):
    def detect(new_claims, existing_pages):
        (page,) = existing_pages
        key = (tuple(new_claims), page["id"], page["content"])
        return [{"existing_page": page["id"]}] if key in flags else []

    return detect


def stub_signal(flags):
    return lambda claim, existing: (claim, existing) in flags


def zero_categories(**counts) -> dict:
    metrics = {}
    for category in CATEGORY_LABEL:
        metrics[f"rows_{category}"] = 0
        metrics[f"flagged_{category}"] = 0
    metrics.update({k.replace("__", "-"): v for k, v in counts.items()})
    return metrics


def test_both_arms_report_hand_computed_counts_ratios_and_per_category_rows(
    probe, tmp_path, monkeypatch
):
    monkeypatch.setattr("kb.ingest.contradiction.detect_contradictions", stub_detect(DETECT_FLAGS))
    monkeypatch.setattr(
        "kb.ingest.contradiction._has_contradiction_signal", stub_signal(SIGNAL_FLAGS)
    )

    result = probe.run(ctx_with_rows(tmp_path, FOUR_ROWS))

    rows = {"rows_negation": 1, "rows_date": 1, "rows_paraphrase": 1, "rows_unrelated__negation": 1}
    detect = zero_categories(**rows, flagged_negation=1, flagged_paraphrase=1)
    detect.update(tp=1, fp=1, fn=1, tn=1, precision=0.5, recall=0.5)
    signal = zero_categories(
        **rows, flagged_negation=1, flagged_date=1, flagged_unrelated__negation=1
    )
    signal.update(tp=2, fp=1, fn=0, tn=1, precision=2 / 3, recall=1.0)
    assert result["arms"] == {
        "detect": {"status": "measured", "cases": 4, "metrics": detect},
        "signal": {"status": "measured", "cases": 4, "metrics": signal},
    }


def test_fixture_with_no_positive_row_reports_zero_recall_and_zero_precision(
    probe, tmp_path, monkeypatch
):
    rows = [
        row("p1", "paraphrase", claim="claim one", existing="existing one"),
        row("p2", "negated-paraphrase", claim="claim two", existing="existing two"),
    ]
    monkeypatch.setattr("kb.ingest.contradiction.detect_contradictions", stub_detect(set()))
    monkeypatch.setattr(
        "kb.ingest.contradiction._has_contradiction_signal",
        stub_signal({("claim two", "existing two")}),
    )

    arms = probe.run(ctx_with_rows(tmp_path, rows))["arms"]

    assert arms["detect"]["metrics"]["recall"] == 0
    assert arms["detect"]["metrics"]["precision"] == 0  # 0 / 0 flagged
    assert arms["signal"]["metrics"]["recall"] == 0
    assert arms["signal"]["metrics"]["precision"] == 0  # 0 / 1 flagged
    assert (arms["signal"]["metrics"]["fp"], arms["signal"]["metrics"]["tn"]) == (1, 1)


# -- acceptance 4: the committed set through the runner, real functions [R3-R6] --


def test_runner_measures_both_arms_on_the_committed_set(bench):
    row_count = len(CASES.read_text(encoding="utf-8").splitlines())

    proc = bench.run(
        "--probe",
        "contradiction",
        "--probes-dir",
        str(PROBES),
        "--wiki",
        str(bench.wiki),
        "--raw",
        str(bench.raw),
        "--out",
        str(bench.out),
        defaults=False,
    )

    assert proc.returncode == 0, proc.output
    record = json.loads((bench.out / "contradiction.json").read_text(encoding="utf-8"))
    assert record["invariants"] == ["I10"]
    assert set(record["arms"]) == {"detect", "signal"}
    for name, arm in record["arms"].items():
        metrics = arm["metrics"]
        assert arm["status"] == "measured", name
        assert arm["cases"] == row_count, name
        assert metrics["tp"] + metrics["fp"] + metrics["fn"] + metrics["tn"] == row_count, name
        rows = sum(v for k, v in metrics.items() if k.startswith("rows_"))
        assert rows == row_count, name
        assert {f"rows_{c}" for c in CATEGORY_LABEL} <= set(metrics), name
