"""Acceptance tests 1-5 of card T1-KBEVAL-BASELINE.

They read the three committed baseline files: `bench/knowledge/summary.json`
(the records of one bench run), `bench/knowledge/labels.jsonl` (the two-labeller
labels of that run's trace sample) and `docs/knowledge-baseline.md` (the report).
"""

from __future__ import annotations

import json
import re
from collections import Counter

import pytest
from conftest import REPO

SUMMARY = REPO / "bench" / "knowledge" / "summary.json"
LABELS = REPO / "bench" / "knowledge" / "labels.jsonl"
REPORT = REPO / "docs" / "knowledge-baseline.md"

PROBES = {"citations", "contradiction", "linker", "provenance", "rebuild", "retrieval", "trace"}
RECORD_KEYS = {"arms", "commit", "dirty", "invariants", "probe"}
LABEL_KEYS = {
    "page",
    "sentence_index",
    "start",
    "end",
    "sha256",
    "band",
    "labelA",
    "labelB",
    "final",
    "ownerRuled",
}
LABEL_SET = {"supported", "partly-supported", "unsupported", "not-a-claim"}
SECTIONS = [
    "Method",
    "Corpus and gaps",
    "Invariants",
    "Contradiction detection",
    "Retrieval",
    "Auto-links",
    "Citations",
    "Traceability",
    "Labels",
    "Rebuild",
    "Provenance",
    "Leads",
    "What these numbers do not show",
]
VERDICTS = ("confirmed", "contradicted", "not decided")
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
PROBE_ALT = "|".join(sorted(PROBES))
# A backticked record path `<probe>.<arm>.<metric>`; arm and metric hold no dot or space.
PATH = re.compile(rf"`({PROBE_ALT})\.([^`.\s]+)\.([^`\s]+)`")
# The same path followed by ` = <number>`: the form a record number is written in.
PATH_VALUE = re.compile(
    rf"`({PROBE_ALT})\.([^`.\s]+)\.([^`\s]+)` = (-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
)


# -- loaders ---------------------------------------------------------------------


def summary() -> dict:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def label_rows() -> list[dict]:
    text = LABELS.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def report() -> str:
    return REPORT.read_text(encoding="utf-8")


def sections(text: str) -> dict[str, str]:
    """Map each `## ` heading of the report to the text up to the next one."""
    parts = re.split(r"^## (.+?)[ \t]*$", text, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def metric(data: dict, probe: str, arm: str, name: str):
    return data["records"][probe]["arms"][arm]["metrics"][name]


# -- acceptance 1 [R1] -----------------------------------------------------------


def test_summary_holds_the_run_commit_and_the_seven_records_of_the_record_shape():
    data = summary()
    assert set(data) == {"records", "run"}
    assert HEX40.fullmatch(data["run"]["commit"]), data["run"]["commit"]
    assert set(data["records"]) == PROBES
    for name, record in data["records"].items():
        assert set(record) == RECORD_KEYS, name
        assert record["probe"] == name
        assert record["commit"] == data["run"]["commit"], name
        assert len(record["arms"]) >= 1, name


def test_summary_run_holds_the_dirty_flag_and_the_two_corpus_counts():
    run = summary()["run"]
    assert set(run) == {"commit", "dirty", "raw_files", "wiki_md_files", "wiki_page_files"}
    assert isinstance(run["dirty"], bool)
    for key in ("raw_files", "wiki_md_files", "wiki_page_files"):
        assert isinstance(run[key], int) and run[key] > 0, key
    assert run["wiki_page_files"] <= run["wiki_md_files"]


# -- acceptance 2 [R2] -----------------------------------------------------------


def test_each_label_row_has_the_ten_keys_and_no_sentence_text():
    rows = label_rows()
    assert rows, "labels.jsonl has no rows"
    for i, row in enumerate(rows, start=1):
        assert set(row) == LABEL_KEYS, f"line {i}"
        assert HEX64.fullmatch(row["sha256"]), f"line {i}"
        for key in ("sentence_index", "start", "end"):
            assert isinstance(row[key], int) and not isinstance(row[key], bool), f"line {i}"
        assert 0 <= row["start"] < row["end"], f"line {i}"


def test_label_row_count_equals_the_trace_sample_size_of_the_run():
    data = summary()
    assert "trace" in data["records"], "summary.json has no trace record"
    expected = metric(data, "trace", "containment", "sample_sentences")
    assert len(label_rows()) == expected


def test_label_rows_are_unique_per_page_and_sentence():
    rows = label_rows()
    assert rows, "labels.jsonl has no rows"
    keys = [(row["page"], row["sentence_index"]) for row in rows]
    assert len(set(keys)) == len(keys)


# -- acceptance 3 [R3] -----------------------------------------------------------


def final_rule_errors(rows: list[dict]) -> list[str]:
    """Return one message per row that breaks the R3 rule for labels and `final`."""
    errors = []
    for i, row in enumerate(rows, start=1):
        if row["labelA"] not in LABEL_SET or row["labelB"] not in LABEL_SET:
            errors.append(f"line {i}: label outside the closed set")
        elif not isinstance(row["ownerRuled"], bool):
            errors.append(f"line {i}: ownerRuled is not a boolean")
        elif row["ownerRuled"]:
            if row["final"] not in LABEL_SET:
                errors.append(f"line {i}: owner-ruled final outside the closed set")
        elif row["labelA"] == row["labelB"]:
            if row["final"] != row["labelA"]:
                errors.append(f"line {i}: agreed labels but final differs")
        elif row["final"] is not None:
            errors.append(f"line {i}: labels differ, no ruling, final is not null")
    return errors


def fixture_row(label_a: str, label_b: str, final, owner_ruled: bool) -> dict:
    return {"labelA": label_a, "labelB": label_b, "final": final, "ownerRuled": owner_ruled}


def test_labels_are_in_the_closed_set_and_final_follows_the_rule():
    rows = label_rows()
    assert rows, "labels.jsonl has no rows"
    assert final_rule_errors(rows) == []


def test_final_rule_rejects_an_owner_ruling_that_overrides_agreed_labels():
    # R3: when labelA equals labelB, final is that label whatever ownerRuled says.
    bad = fixture_row("supported", "supported", "unsupported", True)
    assert len(final_rule_errors([bad])) == 1


def test_final_rule_accepts_an_owner_ruling_on_differing_labels_and_null_without_one():
    rows = [
        fixture_row("supported", "partly-supported", "unsupported", True),
        fixture_row("supported", "partly-supported", None, False),
        fixture_row("not-a-claim", "not-a-claim", "not-a-claim", False),
        fixture_row("not-a-claim", "not-a-claim", "not-a-claim", True),
    ]
    assert final_rule_errors(rows) == []


# -- acceptance 4 [R4] [R5] [R6] ------------------------------------------------


def test_report_has_the_thirteen_sections_in_order():
    headings = re.findall(r"^## (.+?)[ \t]*$", report(), flags=re.MULTILINE)
    assert headings == SECTIONS


def test_every_backticked_record_path_in_the_report_is_in_summary():
    data = summary()
    paths = PATH.findall(report())
    assert paths, "the report names no record path"
    missing = []
    for probe, arm, name in paths:
        arms = data["records"].get(probe, {}).get("arms", {})
        if name not in arms.get(arm, {}).get("metrics", {}):
            missing.append(f"{probe}.{arm}.{name}")
    assert missing == []


def test_every_record_number_in_the_report_is_the_exact_text_of_its_summary_value():
    # The value is written exactly as json.dumps prints it from summary.json: no rounding.
    data = summary()
    pairs = PATH_VALUE.findall(report())
    assert pairs, "the report writes no record number beside its path"
    wrong = []
    for probe, arm, name, written in pairs:
        value = data["records"].get(probe, {}).get("arms", {}).get(arm, {})
        value = value.get("metrics", {}).get(name)
        if value is None or written != json.dumps(value):
            wrong.append((f"{probe}.{arm}.{name}", written, value))
    assert wrong == []


def test_invariants_section_holds_i1_to_i11_once_each_with_i5_and_i7_unmeasured():
    body = sections(report()).get("Invariants", "")
    ids = Counter(re.findall(r"\bI(\d+)\b", body))
    assert {f"I{n}": ids.get(str(n), 0) for n in range(1, 12)} == {f"I{n}": 1 for n in range(1, 12)}
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\|\s*I(\d+)\b.*$", body, re.MULTILINE)}
    assert "unmeasured" in rows.get("5", "")
    assert "unmeasured" in rows.get("7", "")


def test_report_states_the_run_commit_and_the_corpus_counts():
    data = summary()
    text = report()
    run = data["run"]
    assert run["commit"] in text
    for key in ("raw_files", "wiki_md_files", "wiki_page_files"):
        assert f"`run.{key}` = {run[key]}" in text, key
    assert f"`run.dirty` = {str(run['dirty']).lower()}" in text


def test_every_unmeasured_arm_is_named_in_the_report_with_its_reason():
    data = summary()
    text = report()
    unmeasured = [
        (probe, arm, body["reason"])
        for probe, record in data["records"].items()
        for arm, body in record["arms"].items()
        if body["status"] == "unmeasured"
    ]
    assert unmeasured, "summary.json has no unmeasured arm"
    for probe, arm, reason in unmeasured:
        assert f"`{probe}.{arm}` unmeasured: {reason}" in text, (probe, arm)


def test_leads_section_gives_each_of_the_eight_leads_one_verdict():
    body = sections(report()).get("Leads", "")
    entries = re.split(r"^### ", body, flags=re.MULTILINE)[1:]
    numbers = [int(re.match(r"Lead (\d+)", e).group(1)) for e in entries if re.match(r"Lead \d", e)]
    assert numbers == list(range(1, 9))
    for entry in entries:
        found = re.findall(r"^Verdict: (.+?)\.?$", entry, flags=re.MULTILINE)
        assert len(found) == 1 and found[0] in VERDICTS, entry.splitlines()[0]
        assert PATH.search(entry) or "unmeasured" in entry, entry.splitlines()[0]


# -- acceptance 5 [R5] -----------------------------------------------------------


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    count_a, count_b = Counter(a), Counter(b)
    expected = sum(count_a[k] * count_b[k] for k in LABEL_SET) / (n * n)
    return (observed - expected) / (1 - expected)


def test_kappa_helper_matches_a_worked_example():
    # 10 items: 6 agree. A = 5 supported, 5 unsupported; B = 5 supported, 5 unsupported.
    # p_o = 0.6, p_e = 0.5 * 0.5 + 0.5 * 0.5 = 0.5, kappa = 0.1 / 0.5 = 0.2.
    a = ["supported"] * 5 + ["unsupported"] * 5
    b = ["supported"] * 3 + ["unsupported"] * 2 + ["supported"] * 2 + ["unsupported"] * 3
    assert cohen_kappa(a, b) == pytest.approx(0.2)


def test_labels_section_states_agreement_kappa_and_null_count_recomputed_from_labels():
    rows = label_rows()
    assert rows, "labels.jsonl has no rows"
    a = [row["labelA"] for row in rows]
    b = [row["labelB"] for row in rows]
    agreement = sum(x == y for x, y in zip(a, b, strict=True)) / len(rows)
    body = sections(report()).get("Labels", "")
    stated_agreement = re.search(r"Raw agreement rate: (-?\d+\.\d\d)\b", body)
    stated_kappa = re.search(r"Cohen's kappa: (-?\d+\.\d\d)\b", body)
    stated_null = re.search(r"Rows with a null final: (\d+)\b", body)
    assert stated_agreement and stated_kappa and stated_null, "Labels section lacks a figure"
    assert stated_agreement.group(1) == f"{agreement:.2f}"
    assert stated_kappa.group(1) == f"{cohen_kappa(a, b):.2f}"
    assert int(stated_null.group(1)) == sum(row["final"] is None for row in rows)


# -- forbid: no number in the report from outside summary.json or labels.jsonl ----

# A number token: digits not preceded by a letter, digit, `#`, `.` or `-` and not
# followed by a letter or digit, so identifiers such as `I5`, `R5`, `T1` and `#154`
# are not read as numbers.
NUMBER = re.compile(r"(?<![\w#.-])-?\d+(?:\.\d+)?(?!\w)")
# Allow-list of identifier patterns, each removed before the scan:
#   a backticked span (record path, file name, command, SHA) unless it is a bare number;
#   `Phase <n>` (the phase name) and `Lead <n>` (the lead numbers of the intent);
#   the two label figures of acceptance 5, checked to two decimals by their own test.
IDENTIFIERS = [
    re.compile(r"`(?!-?\d+(?:\.\d+)?`)[^`\n]+`"),
    re.compile(r"\bPhase \d+\b"),
    re.compile(r"\bLead \d+\b"),
    re.compile(r"Raw agreement rate: -?\d+\.\d\d\b"),
    re.compile(r"Cohen's kappa: -?\d+\.\d\d\b"),
]


def summary_numbers(node) -> set[str]:
    """Every number in summary.json: numeric values and the digits inside its strings."""
    found: set[str] = set()
    if isinstance(node, bool):
        return found
    if isinstance(node, (int, float)):
        found.add(json.dumps(node))
    elif isinstance(node, str):
        found.update(NUMBER.findall(node))
    elif isinstance(node, dict):
        for value in node.values():
            found |= summary_numbers(value)
    elif isinstance(node, list):
        for value in node:
            found |= summary_numbers(value)
    return found


def label_numbers(rows: list[dict]) -> set[str]:
    """Every count the report may take from labels.jsonl."""
    counts = [len(rows), sum(row["final"] is None for row in rows), 0]
    for key in ("labelA", "labelB", "final"):
        counts += Counter(row[key] for row in rows).values()
    counts += Counter((row["band"], row["final"]) for row in rows).values()
    return {str(n) for n in counts}


def stray_numbers(text: str, allowed: set[str]) -> list[str]:
    for pattern in IDENTIFIERS:
        text = pattern.sub(" ", text)
    return [n for n in NUMBER.findall(text) if n not in allowed]


def test_number_scan_flags_a_number_from_outside_the_data():
    allowed = {"0.25", "12", "56"}
    text = "`linker.inject.tp` = 12. Lead 3, Phase 0, I5, R5, #154. n = 56. Took 9 calls, `7`."
    assert stray_numbers(text, allowed) == ["9", "7"]


def test_every_number_in_the_report_comes_from_summary_or_labels():
    allowed = summary_numbers(summary()) | label_numbers(label_rows())
    assert stray_numbers(report(), allowed) == []
