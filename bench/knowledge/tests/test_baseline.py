"""Acceptance tests 1-5 of card T1-KBEVAL-BASELINE, and 2-4 of T0-KBEVAL-RULINGS.

They read the three committed baseline files: `bench/knowledge/summary.json`
(the records of one bench run), `bench/knowledge/labels.jsonl` (the two-labeller
labels of that run's trace sample) and `docs/knowledge-baseline.md` (the report).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter

import pytest
from conftest import REPO
from markdown_it import MarkdownIt

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
        elif row["labelA"] == row["labelB"]:
            # Agreement decides final; an owner ruling applies only to differing labels.
            if row["final"] != row["labelA"]:
                errors.append(f"line {i}: agreed labels but final differs")
        elif row["ownerRuled"]:
            if row["final"] not in LABEL_SET:
                errors.append(f"line {i}: owner-ruled final outside the closed set")
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


# -- T0-KBEVAL-RULINGS acceptance 2 and 3 [R2] [R4] ------------------------------


# The report is read as it renders, through markdown-it-py (CommonMark plus GFM
# tables), not line by line: a hand-written reader missed rows without an opening
# pipe, second tables and other bullet forms (R3 decisions 1 and 2 of this card).
MARKDOWN = MarkdownIt("commonmark").enable("table")
Row = tuple[str, list[str]]
Table = tuple[str, list[str], list[Row]]


def plain(inline) -> str:
    """Rendered text of an inline token. Raw HTML is left out: it does not show as text."""
    parts = []
    for child in inline.children or []:
        if child.type in ("text", "text_special", "code_inline"):
            parts.append(child.content)
        elif child.type == "image":
            # Alt text shows when the image does not load. The image's `content` is the alt
            # source with its markup; its children are that alt parsed, so render those.
            parts.append(plain(child))
        elif child.type in ("softbreak", "hardbreak"):
            parts.append("\n")
    return visible("".join(parts))


def visible(text: str) -> str:
    """`text` as it reads: NFKC-normalised, with format characters (zero-width spaces,
    soft hyphens) removed, so a name cannot be hidden from the checks by them."""
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def rendered(text: str) -> tuple[list[Table], list[str], list[str]]:
    """Every table as (`## ` section, header cells, rows); the text of every inline run
    (table cells included) and of every code or raw-HTML block, which also show; and the
    section of every piece of raw HTML, which can show a table these checks do not read."""
    tokens = MARKDOWN.parse(text)
    tables: list[Table] = []
    texts: list[str] = []
    html: list[str] = []
    section = ""
    cells: list[list[str]] | None = None
    for i, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h2":
            section = plain(tokens[i + 1])
        elif token.type == "table_open":
            cells = []
        elif token.type == "tr_open" and cells is not None:
            cells.append([])
        elif token.type == "table_close" and cells:
            tables.append((section, cells[0], [(r[0], r[1:]) for r in cells[1:]]))
            cells = None
        elif token.type in ("fence", "code_block", "html_block"):
            texts.append(visible(token.content))
            if token.type == "html_block":
                html.append(section)
        elif token.type == "inline":
            texts.append(plain(token))
            html += [section for child in token.children or [] if child.type == "html_inline"]
            if cells:
                cells[-1].append(plain(token).strip())
    return tables, texts, html


def matching_tables(
    text: str, first_header: str, row_names: set[str], label: str
) -> tuple[list[str], list[Row], list[str]]:
    """Header and rows of every table whose header starts with `first_header`; an error
    unless there is exactly one and it is in the Labels section. Rows of every match are
    returned, so a second table's rows are compared too. A row named like one of
    `row_names` (any case) in any other table shows a second value, and is an error."""
    tables = rendered(text)[0]
    found = [t for t in tables if t[1] and t[1][0] == first_header]
    errors = []
    if len(found) != 1:
        errors.append(f"{label}: {len(found)} tables with header {first_header!r}")
    errors += [f"{label}: table under {s!r}" for s, _, _ in found if s != "Labels"]
    others = [t for t in tables if not any(t is f for f in found)]
    errors += [
        f"{label}: row {name!r} in a table with header {header[0]!r}"
        for _, header, other_rows in others
        for name, _ in other_rows
        if name.lower() in row_names
    ]
    if not found:
        return [], [], errors
    return found[0][1], [row for t in found for row in t[2]], errors


def repeated(names: list[str]) -> list[str]:
    return sorted(name for name, n in Counter(names).items() if n > 1)


def figure_errors(text: str, rows: list[dict]) -> list[str]:
    """Each Labels figure must render exactly once, with its value recomputed from `rows`."""
    a = [row["labelA"] for row in rows]
    b = [row["labelB"] for row in rows]
    expected = {
        "Raw agreement rate": f"{sum(x == y for x, y in zip(a, b, strict=True)) / len(rows):.2f}",
        "Cohen's kappa": f"{cohen_kappa(a, b):.2f}",
        "Rows with a null final": str(sum(row["final"] is None for row in rows)),
        "Rows with an owner ruling": str(sum(row["ownerRuled"] is True for row in rows)),
    }
    texts = rendered(text)[1]
    errors = []
    for name, value in expected.items():
        # A figure is found by its name alone (any spacing or case, either apostrophe),
        # whatever follows it, so a second one cannot hide behind a value the check does
        # not parse. The one occurrence must then read `<name>: <value>` exactly.
        words = r"\s+".join(re.escape(w).replace("'", "['’]") for w in name.split())
        pattern = re.compile(words, re.IGNORECASE)
        found = [(t, m.end()) for t in texts for m in pattern.finditer(t)]
        if len(found) != 1:
            errors.append(f"{name}: shown {len(found)} times")
            continue
        t, end = found[0]
        stated = re.match(r":\s*(\S+)", t[end:])
        if not stated or stated.group(1) != value:
            errors.append(f"{name}: reads {t[end : end + 20]!r}, expected ': {value}'")
    return errors


def html_errors(text: str) -> list[str]:
    """Raw HTML anywhere in the report could show a figure or table the checks do not
    read as one; the report holds none."""
    found = rendered(text)[2]
    return [f"raw HTML in sections {sorted(set(found))}"] if found else []


def test_report_holds_no_raw_html():
    assert html_errors(report()) == []


def test_labels_section_renders_each_figure_once_with_its_recomputed_value():
    text = report()
    assert figure_errors(text, label_rows()) == []
    doubled = re.sub(
        r"^(- Rows with an owner ruling: .*\n)",
        r"\1- Rows with an owner ruling: 2\n",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    assert doubled != text and figure_errors(doubled, label_rows()) != []


def test_labels_section_states_owner_ruled_count_recomputed_from_labels():
    rows = label_rows()
    body = sections(report()).get("Labels", "")
    stated = re.search(r"Rows with an owner ruling: (\d+)\b", body)
    assert stated, "Labels section lacks the owner-ruling figure"
    assert int(stated.group(1)) == sum(row["ownerRuled"] is True for row in rows)


def label_table_errors(body: str, rows: list[dict]) -> list[str]:
    """One message per way the label-count table differs from the counts of `rows`."""
    header, table_rows, errors = matching_tables(body, "Label", LABEL_SET | {"null"}, "label table")
    others = [
        t[1]
        for t in rendered(body)[0]
        if t[0] == "Labels" and t[1][:1] not in (["Label"], ["Band"])
    ]
    errors += [f"label table: other table in Labels with header {h}" for h in others]
    if header != ["Label", "labelA", "labelB", "final"]:
        errors.append(f"label table: header {header}")
    names = [name for name, _ in table_rows]
    errors += [f"label table: row {name} appears more than once" for name in repeated(names)]
    if set(names) != LABEL_SET | {"null"}:
        errors.append(f"label table: rows {sorted(names)}")
    counts = {key: Counter(row[key] for row in rows) for key in ("labelA", "labelB", "final")}
    for name, cells in table_rows:
        if name in LABEL_SET:
            expected = [str(counts[key][name]) for key in ("labelA", "labelB", "final")]
        elif name == "null":
            expected = ["", "", str(counts["final"][None])]
        else:
            continue
        if cells != expected:
            errors.append(f"label table: row {name} is {cells}, expected {expected}")
    return errors


def band_table_errors(body: str, rows: list[dict]) -> list[str]:
    """One message per way the `final`-by-band table differs from the counts of `rows`."""
    bands = {row["band"].lower() for row in rows}
    header, table_rows, errors = matching_tables(body, "Band", bands, "band table")
    if not header or header[0] != "Band" or not set(header[1:]) <= LABEL_SET | {"null"}:
        return errors + [f"band table: header {header}"]
    errors += [f"band table: column {name} appears more than once" for name in repeated(header)]
    names = [name for name, _ in table_rows]
    errors += [f"band table: row {name} appears more than once" for name in repeated(names)]
    if set(names) != {row["band"] for row in rows}:
        errors.append(f"band table: rows {sorted(names)}")
    by_band = Counter((row["band"], row["final"]) for row in rows)
    for band, values in table_rows:
        if len(values) != len(header) - 1:
            errors.append(f"band table: row {band} has {len(values)} cells")
            continue
        for column, value in zip(header[1:], values, strict=True):
            expected = str(by_band[(band, None if column == "null" else column)])
            if value != expected:
                errors.append(f"band table: {band}/{column} is {value}, expected {expected}")
        # A band row sums to every row of that band, so no column was left out.
        total = sum(int(v) for v in values if v.isdigit())
        if total != sum(row["band"] == band for row in rows):
            errors.append(f"band table: row {band} sums to {total}")
    return errors


def test_label_count_table_equals_counts_recomputed_from_labels():
    assert label_table_errors(report(), label_rows()) == []


def test_final_by_band_table_equals_counts_recomputed_from_labels():
    assert band_table_errors(report(), label_rows()) == []


def insert_after(text: str, prefix: str, new: str) -> str:
    """`text` with `new` inserted after its one line that starts with `prefix`."""
    lines = text.splitlines(keepends=True)
    hits = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    assert len(hits) == 1, prefix
    return "".join(lines[: hits[0] + 1]) + new + "".join(lines[hits[0] + 1 :])


def test_label_checks_cover_every_rendered_row_table_and_figure():
    # R3 decision 2 of T0-KBEVAL-RULINGS: a row written without its opening pipe, a
    # second table with the same header, and a figure in another bullet, escaped or
    # behind an HTML comment all render (or hide) a value, so each must be caught.
    rows, text = label_rows(), report()
    owner = sum(row["ownerRuled"] is True for row in rows)
    second_label_table = "\n| Label | labelA | labelB | final |\n|---|---|---|---|\n"
    second_band_table = "\n| Band | supported | partly-supported | not-a-claim | null |\n"
    second_band_table += "|---|---|---|---|---|\n"
    label_cases = [
        insert_after(text, "| null |", "supported | 0 | 0 | 0 |\n"),
        insert_after(
            text, "`final` by containment band:", second_label_table + "| supported | 0 | 0 | 0 |\n"
        ),
    ]
    band_cases = [
        insert_after(text, "| low |", "low | 0 | 0 | 0 | 0 |\n"),
        insert_after(text, "Label counts:", second_band_table + "| low | 0 | 0 | 0 | 0 |\n"),
    ]
    hidden = insert_after(
        text, "Figures over all rows", f"\n<!-- Rows with an owner ruling: {owner} -->\n"
    )
    figure_cases = [
        insert_after(
            text, "- Rows with an owner ruling:", f"* Rows with an owner ruling: {owner + 1}\n"
        ),
        insert_after(
            text, "- Rows with an owner ruling:", f"- Rows with an owner ruling\\: {owner + 1}\n"
        ),
        re.sub(
            r"^- Rows with an owner ruling: \d+",
            f"- Rows with an owner ruling: {owner + 1}",
            hidden,
            flags=re.M,
        ),
        # A second figure in a code block, a table cell, with other spacing or case, or
        # with the other apostrophe also shows a second value.
        insert_after(
            text, "- Rows with an owner ruling:", "\n```\nRows with an owner ruling: 9\n```\n"
        ),
        insert_after(text, "| null |", "\n| x |\n|---|\n| Rows with an owner ruling: 9 |\n"),
        insert_after(text, "- Rows with an owner ruling:", "- Rows with an owner ruling : 9\n"),
        insert_after(text, "- Rows with an owner ruling:", "- rows with an owner ruling: 9\n"),
        insert_after(text, "- Rows with an owner ruling:", "- Cohen’s kappa: 0.10\n"),
    ]
    html_cases = [
        hidden,
        insert_after(
            text,
            "`final` by containment band:",
            "\n<table><tr><td>supported</td><td>0</td></tr></table>\n",
        ),
    ]
    for case in label_cases:
        assert case != text and label_table_errors(case, rows) != []
    for case in band_cases:
        assert case != text and band_table_errors(case, rows) != []
    for case in figure_cases:
        assert case != text and figure_errors(case, rows) != []
    for case in html_cases:
        assert case != text and html_errors(case) != []


def test_label_checks_find_figures_by_name_and_label_rows_in_any_table():
    # R3 decision 3 of T0-KBEVAL-RULINGS: a second figure is a second figure whatever
    # follows its name (a signed value, a value in the next paragraph, image alt text),
    # and a row named after a label or a band shows a second value in any table.
    rows, text = label_rows(), report()
    figure = "- Rows with an owner ruling:"
    figure_cases = [
        insert_after(text, figure, "* Rows with an owner ruling: +2\n"),
        insert_after(text, figure, "* Rows with a null final: +2\n"),
        insert_after(text, figure, "\nRows with an owner ruling:\n\n2\n"),
        insert_after(text, figure, "\n![Rows with an owner ruling: 2](x.png)\n"),
        insert_after(text, figure, "* Rows with an own​er ruling: 2\n"),
    ]
    label_cases = [
        insert_after(
            text,
            "`final` by containment band:",
            "\n| label | labelA | labelB | final |\n|---|---|---|---|\n| supported | 0 | 0 | 0 |\n",
        ),
        insert_after(
            text,
            "Every disagreement",
            "\n| Count | labelA | labelB | final |\n|---|---|---|---|\n| supported | 0 | 0 | 0 |\n",
        ),
    ]
    band_cases = [
        insert_after(
            text, "Every disagreement", "\n| Group | supported |\n|---|---|\n| low | 0 |\n"
        ),
    ]
    for case in figure_cases:
        assert case != text and figure_errors(case, rows) != []
    for case in label_cases:
        assert case != text and label_table_errors(case, rows) != []
    for case in band_cases:
        assert case != text and band_table_errors(case, rows) != []


# -- T1-KBEVAL-ALTFIG acceptance 1 and 2 [R1] ------------------------------------


@pytest.mark.parametrize(
    ("figure", "alt"),
    [
        ("- Rows with an owner ruling:", "Rows with an **owner** ruling: 2"),
        ("- Rows with a null final:", "Rows with a *null* final: 2"),
    ],
    ids=["owner-ruling", "null-final"],
)
def test_a_second_figure_in_formatted_image_alt_text_is_found(figure, alt):
    # Issue #163: alt text shows as it renders when the image does not load, so
    # `**owner**` reads "owner" and the figure name is shown a second time.
    rows, text = label_rows(), report()
    case = insert_after(text, figure, f"\n![{alt}](x.png)\n")
    assert case != text and figure_errors(case, rows) != []


def first_inline(text: str):
    """The first inline token markdown-it-py parses from `text`."""
    return next(token for token in MARKDOWN.parse(text) if token.type == "inline")


@pytest.mark.parametrize(
    ("source", "expected"),
    [("![a **b** `c`](x.png)", "a b c"), ("![a <b>x</b>](x.png)", "a x")],
    ids=["markup", "raw-html"],
)
def test_plain_renders_image_alt_text_as_it_shows(source, expected):
    assert plain(first_inline(source)) == expected


def test_table_checks_reject_an_extra_row_placed_before_the_correct_one():
    # R3 decision 1 of T0-KBEVAL-RULINGS: a wrong row ahead of the right one with the
    # same name must not pass, nor may an exact copy of a correct row.
    rows, body = label_rows(), report()
    once = {"count": 1, "flags": re.M}
    wrong_label = re.sub(r"^\| supported \|", "| supported | 0 | 0 | 0 |\n\\g<0>", body, **once)
    wrong_band = re.sub(r"^\| low \|", "| low | 0 | 0 | 0 | 0 |\n\\g<0>", body, **once)
    copy_label = re.sub(r"^(\| supported \|.*\n)", r"\1\1", body, **once)
    copy_band = re.sub(r"^(\| low \|.*\n)", r"\1\1", body, **once)
    assert wrong_label != body and wrong_band != body
    assert copy_label != body and copy_band != body
    assert label_table_errors(wrong_label, rows) != []
    assert band_table_errors(wrong_band, rows) != []
    assert label_table_errors(copy_label, rows) != []
    assert band_table_errors(copy_band, rows) != []


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
    counts = [
        len(rows),
        sum(row["final"] is None for row in rows),
        sum(row["ownerRuled"] is True for row in rows),
        0,
    ]
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
