"""Acceptance tests 1-4 of card T1-KBEVAL-LINKER for the `linker` probe."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import frontmatter
import pytest
from conftest import REPO

PROBES = REPO / "bench" / "knowledge" / "probes"
PROBE = PROBES / "linker.py"
CASES = REPO / "bench" / "knowledge" / "data" / "linker" / "cases.jsonl"

CATEGORY_LINK = {
    "proper-mention": True,
    "cjk-in-cjk": True,
    "common-word": False,
    "case-variant": False,
    "inside-code": False,
    "already-linked": False,
}
FIELDS = ("id", "category", "title", "target_id", "body", "should_link", "why")
STRING_FIELDS = ("id", "category", "title", "target_id", "body", "why")
CJK = re.compile(r"[㐀-䶿一-鿿]")
CODE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]+`", re.DOTALL)


@pytest.fixture
def probe():
    """The probe module loaded in-process from its file, as the runner loads it."""
    name = "kbeval_probe_linker_under_test"
    spec = importlib.util.spec_from_file_location(name, PROBE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(name, None)


@pytest.fixture(autouse=True)
def no_real_inject(monkeypatch):
    """In-process tests never run the real linker; a test that needs a call installs a stub."""

    def refuse(*args, **kwargs):
        raise AssertionError("the real inject_wikilinks was called in-process")

    monkeypatch.setattr("kb.compile.linker.inject_wikilinks", refuse)


def committed_rows() -> list[dict]:
    return [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]


def row(rid: str, category: str, title: str, target_id: str, body: str, **override) -> dict:
    data = {
        "id": rid,
        "category": category,
        "title": title,
        "target_id": target_id,
        "body": body,
        "should_link": CATEGORY_LINK[category],
        "why": "fixture row",
    }
    data.update(override)
    return data


def ctx_with(tmp_path: Path, lines: list[str]) -> SimpleNamespace:
    data = tmp_path / "data"
    data.mkdir()
    (data / "cases.jsonl").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    return SimpleNamespace(tmp=tmp, data=data, wiki=tmp_path, raw=tmp_path, out=tmp_path)


def ctx_with_rows(tmp_path: Path, rows: list[dict]) -> SimpleNamespace:
    return ctx_with(tmp_path, [json.dumps(r, ensure_ascii=False) for r in rows])


def stub_inject(link=(), touch=(), calls=None):
    """Replace inject_wikilinks: append a link for titles in `link`, plain text for `touch`.

    Each call records its arguments and every page under the wiki directory as it was
    when the call began.
    """

    def inject(*args, **kwargs):
        title, target_id, wiki_dir = args
        root = Path(wiki_dir)
        pages = {
            p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(root.rglob("*.md"))
        }
        if calls is not None:
            calls.append((args, kwargs, pages))
        edited = []
        for rel, text in pages.items():
            if rel == f"{target_id}.md":
                continue
            if title in link:
                added = f"\n\nSee [[{target_id}]]."
            elif title in touch:
                added = "\n\nEdited without adding a link."
            else:
                continue
            (root / rel).write_text(text + added, encoding="utf-8")
            edited.append(rel.removesuffix(".md"))
        return edited

    return inject


# -- acceptance 1: the committed case set [R1] [R2] -------------------------------


def test_committed_case_set_has_seven_fields_unique_ids_and_ten_rows_per_category():
    rows = committed_rows()

    assert all(isinstance(r, dict) and set(r) == set(FIELDS) for r in rows)
    assert all(isinstance(r[f], str) and r[f].strip() for r in rows for f in STRING_FIELDS)
    assert all(r["should_link"] is CATEGORY_LINK[r["category"]] for r in rows)
    assert len({r["id"] for r in rows}) == len(rows)
    for category in CATEGORY_LINK:
        assert sum(r["category"] == category for r in rows) >= 10, category


def test_every_cjk_title_is_chinese_with_a_chinese_character_before_and_after_each_use():
    rows = [r for r in committed_rows() if r["category"] == "cjk-in-cjk"]

    for r in rows:
        title, body = r["title"], r["body"]
        assert all(CJK.fullmatch(ch) for ch in title), r["id"]
        starts = [m.start() for m in re.finditer(re.escape(title), body)]
        assert starts, r["id"]
        for start in starts:
            end = start + len(title)
            assert start > 0 and CJK.fullmatch(body[start - 1]), r["id"]
            assert end < len(body) and CJK.fullmatch(body[end]), r["id"]


def word(title: str, flags: int = 0) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(title)}(?!\w)", flags)


def test_english_rows_hold_the_title_in_the_form_their_category_names():
    for r in committed_rows():
        title, body, category = r["title"], r["body"], r["category"]
        if category in ("proper-mention", "common-word", "case-variant"):
            # Plain prose: no code and no wikilink for the matcher to skip.
            assert "`" not in body and "~~~" not in body and "[[" not in body, r["id"]
        if category in ("proper-mention", "common-word"):
            assert word(title).search(body), r["id"]
        if category == "case-variant":
            assert word(title, re.IGNORECASE).search(body), r["id"]
            assert not word(title).search(body), r["id"]
        if category == "inside-code":
            assert word(title, re.IGNORECASE).search(body), r["id"]
            assert not word(title, re.IGNORECASE).search(CODE.sub(" ", body)), r["id"]
            assert "[[" not in body, r["id"]
        if category == "already-linked":
            link = re.compile(rf"\[\[{re.escape(r['target_id'])}(\|[^\]]*)?\]\]")
            assert link.search(body), r["id"]
            assert word(title).search(link.sub(" ", body)), r["id"]


def test_committed_case_set_loads_through_the_probe_without_error(probe, tmp_path, monkeypatch):
    monkeypatch.setattr("kb.compile.linker.inject_wikilinks", stub_inject())
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    ctx = SimpleNamespace(tmp=tmp, data=CASES.parent)

    arm = probe.run(ctx)["arms"]["inject"]

    assert arm["cases"] == len(committed_rows())


# -- acceptance 2: one ValueError per malformed-line cause [R2] -----------------

GOOD = row("a", "proper-mention", "Alpha", "concepts/alpha", "Alpha is here.")


def assert_rejected(probe, ctx, line_number: int) -> None:
    with pytest.raises(ValueError) as caught:
        probe.run(ctx)
    message = str(caught.value)
    assert "cases.jsonl" in message
    assert f"line {line_number}" in message


def test_line_that_is_not_a_json_object_is_rejected_with_file_and_line(probe, tmp_path):
    ctx = ctx_with(tmp_path, [json.dumps(GOOD), '["a", "list"]'])
    assert_rejected(probe, ctx, 2)


def test_line_that_is_not_json_at_all_is_rejected_with_file_and_line(probe, tmp_path):
    ctx = ctx_with(tmp_path, ["{not json"])
    assert_rejected(probe, ctx, 1)


def test_blank_line_is_rejected_with_file_and_line(probe, tmp_path):
    other = {**GOOD, "id": "b"}
    ctx = ctx_with(tmp_path, [json.dumps(GOOD), "", json.dumps(other)])
    assert_rejected(probe, ctx, 2)


@pytest.mark.parametrize("field", FIELDS)
def test_row_missing_a_field_is_rejected_with_file_and_line(probe, tmp_path, field):
    incomplete = {**GOOD, "id": "c"}
    del incomplete[field]
    ctx = ctx_with_rows(tmp_path, [GOOD, {**GOOD, "id": "b"}, incomplete])
    assert_rejected(probe, ctx, 3)


@pytest.mark.parametrize("field", STRING_FIELDS)
def test_text_field_that_is_not_a_string_is_rejected_with_file_and_line(probe, tmp_path, field):
    ctx = ctx_with_rows(tmp_path, [{**GOOD, field: ["not", "a", "string"]}])
    assert_rejected(probe, ctx, 1)


def test_repeated_id_is_rejected_with_file_and_line(probe, tmp_path):
    ctx = ctx_with_rows(tmp_path, [GOOD, {**GOOD, "id": "b"}, {**GOOD, "title": "Other"}])
    assert_rejected(probe, ctx, 3)


def test_unknown_category_is_rejected_with_file_and_line(probe, tmp_path):
    ctx = ctx_with_rows(tmp_path, [GOOD, {**GOOD, "id": "b", "category": "nickname"}])
    assert_rejected(probe, ctx, 2)


@pytest.mark.parametrize("category", CATEGORY_LINK)
def test_should_link_that_is_not_the_categorys_value_is_rejected(probe, tmp_path, category):
    bad = {**GOOD, "id": "b", "category": category, "should_link": not CATEGORY_LINK[category]}
    ctx = ctx_with_rows(tmp_path, [GOOD, bad])
    assert_rejected(probe, ctx, 2)


@pytest.mark.parametrize("value", ["true", 1, None])
def test_should_link_that_is_not_a_boolean_is_rejected(probe, tmp_path, value):
    ctx = ctx_with_rows(tmp_path, [GOOD, {**GOOD, "id": "b", "should_link": value}])
    assert_rejected(probe, ctx, 2)


@pytest.mark.parametrize(
    "target_id", ["../outside", "concepts/../../x", "Concepts/Alpha", "alpha", "notes/alpha"]
)
def test_target_id_that_is_not_a_wiki_page_id_is_rejected(probe, tmp_path, target_id):
    ctx = ctx_with_rows(tmp_path, [GOOD, {**GOOD, "id": "b", "target_id": target_id}])
    assert_rejected(probe, ctx, 2)


# -- acceptance 3: hand-computed metrics with a stubbed inject_wikilinks [R3] [R4] --

FOUR_ROWS = [
    row("r1", "proper-mention", "Alpha", "concepts/alpha", "Alpha is a fixture term."),
    row("r2", "cjk-in-cjk", "甲乙丙", "concepts/jia-yi-bing", "我们用甲乙丙来测试。"),
    row("r3", "common-word", "Gamma", "concepts/gamma", "Gamma rays reach the ground."),
    row("r4", "already-linked", "Delta", "concepts/delta", "See [[concepts/delta]] for Delta."),
]


def category_metrics(**counts) -> dict:
    """Every rows_/linked_ key at 0, then the given counts (`__` stands for `-`)."""
    metrics = {}
    for category in CATEGORY_LINK:
        metrics[f"rows_{category}"] = 0
        metrics[f"linked_{category}"] = 0
    metrics.update({k.replace("__", "-"): v for k, v in counts.items()})
    return metrics


def test_inject_arm_reports_hand_computed_counts_ratios_and_per_category_rows(
    probe, tmp_path, monkeypatch
):
    # r1 and r3 gain a link; r4 is edited but keeps its one link, so it is not linked.
    monkeypatch.setattr(
        "kb.compile.linker.inject_wikilinks", stub_inject(link={"Alpha", "Gamma"}, touch={"Delta"})
    )

    result = probe.run(ctx_with_rows(tmp_path, FOUR_ROWS))

    metrics = category_metrics(
        rows_proper__mention=1,
        rows_cjk__in__cjk=1,
        rows_common__word=1,
        rows_already__linked=1,
        linked_proper__mention=1,
        linked_common__word=1,
    )
    metrics.update(tp=1, fp=1, fn=1, tn=1, precision=0.5, recall=0.5)
    assert result == {
        "invariants": ["I11"],
        "arms": {"inject": {"status": "measured", "cases": 4, "metrics": metrics}},
    }


def test_inject_arm_keeps_false_positives_and_misses_apart(probe, tmp_path, monkeypatch):
    rows = [
        row("b1", "proper-mention", "Alpha", "concepts/alpha", "Alpha is a fixture term."),
        row("b2", "case-variant", "EPS", "concepts/eps", "The eps value is small."),
        row("b3", "inside-code", "Zeta", "concepts/zeta", "Run `zeta --help` first."),
        row("b4", "cjk-in-cjk", "甲乙丙", "concepts/jia-yi-bing", "我们用甲乙丙来测试。"),
    ]
    monkeypatch.setattr(
        "kb.compile.linker.inject_wikilinks", stub_inject(link={"Alpha", "EPS", "Zeta"})
    )

    arm = probe.run(ctx_with_rows(tmp_path, rows))["arms"]["inject"]

    metrics = category_metrics(
        rows_proper__mention=1,
        rows_case__variant=1,
        rows_inside__code=1,
        rows_cjk__in__cjk=1,
        linked_proper__mention=1,
        linked_case__variant=1,
        linked_inside__code=1,
    )
    metrics.update(tp=1, fp=2, fn=1, tn=0, precision=1 / 3, recall=0.5)
    assert arm == {"status": "measured", "cases": 4, "metrics": metrics}


def test_fixture_with_no_positive_row_and_no_link_reports_zero_ratios(probe, tmp_path, monkeypatch):
    rows = [
        row("n1", "common-word", "Gamma", "concepts/gamma", "Gamma rays reach the ground."),
        row("n2", "inside-code", "Zeta", "concepts/zeta", "Run `zeta --help` first."),
    ]
    monkeypatch.setattr("kb.compile.linker.inject_wikilinks", stub_inject())

    metrics = probe.run(ctx_with_rows(tmp_path, rows))["arms"]["inject"]["metrics"]

    # precision is 0 / 0 linked rows and recall 0 / 0 positive rows, both reported as 0.
    names = ("tp", "fp", "fn", "tn", "precision", "recall")
    assert {name: metrics.get(name) for name in names} == {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 2,
        "precision": 0,
        "recall": 0,
    }


def test_inject_is_called_once_per_row_with_title_target_and_wiki_dir(probe, tmp_path, monkeypatch):
    calls: list = []
    monkeypatch.setattr("kb.compile.linker.inject_wikilinks", stub_inject(calls=calls))

    probe.run(ctx_with_rows(tmp_path, FOUR_ROWS))

    assert [(args[:2], len(args), kwargs) for args, kwargs, _ in calls] == [
        (("Alpha", "concepts/alpha"), 3, {}),
        (("甲乙丙", "concepts/jia-yi-bing"), 3, {}),
        (("Gamma", "concepts/gamma"), 3, {}),
        (("Delta", "concepts/delta"), 3, {}),
    ]


def test_each_call_sees_a_fresh_wiki_with_the_target_page_and_the_body_page(
    probe, tmp_path, monkeypatch
):
    from kb.utils.pages import WIKI_SUBDIRS

    calls: list = []
    monkeypatch.setattr("kb.compile.linker.inject_wikilinks", stub_inject(calls=calls))
    ctx = ctx_with_rows(tmp_path, FOUR_ROWS)

    probe.run(ctx)

    assert len(calls) == len(FOUR_ROWS)
    wiki_dirs = [Path(args[2]).resolve() for args, _, _ in calls]
    assert len(set(wiki_dirs)) == len(FOUR_ROWS)
    for r, wiki_dir, (_, _, pages) in zip(FOUR_ROWS, wiki_dirs, calls, strict=True):
        assert wiki_dir.is_relative_to(Path(ctx.tmp).resolve()), r["id"]
        target = f"{r['target_id']}.md"
        assert len(pages) == 2 and target in pages, (r["id"], sorted(pages))
        assert frontmatter.loads(pages[target]).metadata["title"] == r["title"], r["id"]
        (other,) = set(pages) - {target}
        assert other.split("/")[0] in WIKI_SUBDIRS, (r["id"], other)
        assert frontmatter.loads(pages[other]).content == r["body"], r["id"]


# -- acceptance 4: the committed set through the runner, real function [R3-R5] --


def test_runner_measures_the_inject_arm_on_the_committed_set(bench):
    rows = committed_rows()

    proc = bench.run(
        "--probe",
        "linker",
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
    record = json.loads((bench.out / "linker.json").read_text(encoding="utf-8"))
    assert record["invariants"] == ["I11"]
    assert set(record["arms"]) == {"inject"}
    arm = record["arms"]["inject"]
    metrics = arm["metrics"]
    assert arm["status"] == "measured"
    assert arm["cases"] == len(rows)
    assert metrics["tp"] + metrics["fp"] + metrics["fn"] + metrics["tn"] == len(rows)
    for category, link in CATEGORY_LINK.items():
        assert metrics[f"rows_{category}"] == sum(r["category"] == category for r in rows)
        assert 0 <= metrics[f"linked_{category}"] <= metrics[f"rows_{category}"]
    linked_pos = sum(metrics[f"linked_{c}"] for c, link in CATEGORY_LINK.items() if link)
    linked_neg = sum(metrics[f"linked_{c}"] for c, link in CATEGORY_LINK.items() if not link)
    assert (metrics["tp"], metrics["fp"]) == (linked_pos, linked_neg)
