"""Acceptance tests 1-8 of card T1-KBEVAL-TRACE for `bench/knowledge/probes/trace.py`."""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import REPO

PROBE = REPO / "bench" / "knowledge" / "probes" / "trace.py"
PROBES = PROBE.parent
SAMPLE = "trace-sample.jsonl"
NO_SOURCE = object()
ROW_FIELDS = {
    "page",
    "sentence_index",
    "start",
    "end",
    "sha256",
    "band",
    "containment",
    "sources",
    "text",
}
REF_KINDS = ("text", "undecodable", "non_text", "missing", "url", "outside")
CONTAINMENT_METRICS = {
    "pages_unparsed",
    "pages_no_source_field",
    "pages_no_text_source",
    *(f"refs_{kind}" for kind in REF_KINDS),
    "refs_total",
    "sentences",
    "sentences_short",
    "sentences_no_text_source",
    "band_high",
    "band_mid",
    "band_low",
    "sample_pages",
    "sample_sentences",
}

# Two sentences copied from SOURCE_EN, so both fall in the high band.
TWO = (
    "The compiled wiki keeps every page in plain markdown files. "
    "Each page lists the raw sources it was written from."
)
SOURCE_EN = "Intro. " + TWO + " Closing remarks of the source."


# -- helpers ---------------------------------------------------------------------


@pytest.fixture
def probe():
    name = "kbeval_probe_trace_under_test"
    spec = importlib.util.spec_from_file_location(name, PROBE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(name, None)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def page_text(body: str, source=NO_SOURCE) -> str:
    lines = ["---", 'title: "Fixture page"']
    if source is not NO_SOURCE:
        lines.append("source:")
        lines += [f"  - {json.dumps(ref)}" for ref in source]
    lines += ["---", body, ""]
    return "\n".join(lines)


def make_ctx(tmp_path: Path, templates: Path | None = None) -> SimpleNamespace:
    dirs = {name: tmp_path / name for name in ("tmp", "data", "wiki", "raw", "out")}
    for path in dirs.values():
        path.mkdir()
    if templates is None:
        templates = tmp_path / "templates"
        templates.mkdir()
    return SimpleNamespace(templates=templates, **dirs)


def containment_arm(result: dict) -> dict:
    return result["arms"]["containment"]


def metrics(result: dict) -> dict:
    return containment_arm(result)["metrics"]


def sample_rows(ctx) -> list[dict]:
    text = (ctx.out / SAMPLE).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def refs_counts(m: dict) -> dict:
    return {kind: m[f"refs_{kind}"] for kind in REF_KINDS}


# -- acceptance 1: pages, page ids, unparsed and source-less pages [R1] ------------


def test_pages_are_md_files_in_subdirectories_with_id_subdirectory_slash_stem(probe, tmp_path):
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "articles" / "src.md", SOURCE_EN)
    write(ctx.wiki / "index.md", page_text(TWO, ["raw/articles/src.md"]))
    write(ctx.wiki / "concepts" / "alpha.md", page_text(TWO, ["raw/articles/src.md"]))
    write(ctx.wiki / "entities" / "broken.md", "---\ntitle: [unclosed\n---\nBody text.\n")
    write(ctx.wiki / "summaries" / "nosource.md", page_text(TWO))

    result = probe.run(ctx)

    assert containment_arm(result)["status"] == "measured"
    assert containment_arm(result)["cases"] == 3
    assert metrics(result)["pages_unparsed"] == 1
    assert metrics(result)["pages_no_source_field"] == 1
    assert {row["page"] for row in sample_rows(ctx)} == {"concepts/alpha"}


@pytest.mark.parametrize(
    "content",
    [
        "---\ntitle: [unclosed\n---\nBody text here.\n",
        "---\ntitle: never closed\nsource:\n  - raw/a.md\nBody text here.\n",
        "---\n- a list\n- not a mapping\n---\nBody text here.\n",
        b"---\ntitle: x\n---\nBody \xff\xfe text.\n",
    ],
    ids=["yaml-error", "unclosed-block", "not-a-mapping", "not-utf8"],
)
def test_page_whose_frontmatter_does_not_parse_is_in_pages_unparsed(probe, tmp_path, content):
    ctx = make_ctx(tmp_path)
    write(ctx.wiki / "concepts" / "bad.md", content)

    result = probe.run(ctx)

    assert containment_arm(result)["cases"] == 1
    assert metrics(result)["pages_unparsed"] == 1
    assert metrics(result)["pages_no_source_field"] == 0
    assert metrics(result)["refs_total"] == 0
    assert metrics(result)["sentences"] == 0


@pytest.mark.parametrize(
    "content",
    [
        "A page with no frontmatter at all has this sentence.\n",
        '---\ntitle: "No source key"\n---\nA page without a source key has this.\n',
        "---\ntitle: x\nsource: []\n---\nA page with an empty source list has this.\n",
        "---\ntitle: x\nsource:\n---\nA page with a null source field has this.\n",
    ],
    ids=["no-frontmatter", "no-key", "empty-list", "null"],
)
def test_page_with_no_ref_is_in_pages_no_source_field(probe, tmp_path, content):
    ctx = make_ctx(tmp_path)
    write(ctx.wiki / "concepts" / "plain.md", content)

    result = probe.run(ctx)

    assert metrics(result)["pages_no_source_field"] == 1
    assert metrics(result)["pages_unparsed"] == 0
    assert metrics(result)["refs_total"] == 0


def test_source_given_as_one_string_is_one_ref(probe, tmp_path):
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "articles" / "src.md", SOURCE_EN)
    write(ctx.wiki / "concepts" / "one.md", f"---\nsource: raw/articles/src.md\n---\n{TWO}\n")

    result = probe.run(ctx)

    assert metrics(result)["refs_total"] == 1
    assert metrics(result)["refs_text"] == 1
    assert metrics(result)["band_high"] == 2


# -- acceptance 2: the six ref kinds, no file-system call on outside or url [R2] ---


@pytest.fixture
def fs_calls(monkeypatch):
    """Record (call, path) for Path.stat, Path.exists and open; pass every call through."""
    calls: list[tuple[str, str]] = []
    real_stat, real_exists, real_open = Path.stat, Path.exists, builtins.open

    def stat(self, *args, **kwargs):
        calls.append(("stat", str(self)))
        return real_stat(self, *args, **kwargs)

    def exists(self, *args, **kwargs):
        calls.append(("exists", str(self)))
        return real_exists(self, *args, **kwargs)

    def fake_open(file, *args, **kwargs):
        calls.append(("open", str(file)))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(builtins, "open", fake_open)
    return calls


def test_one_ref_of_each_kind_is_counted_once_and_outside_and_url_are_never_touched(
    probe, tmp_path, fs_calls
):
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "articles" / "text-src.md", SOURCE_EN)
    write(ctx.raw / "articles" / "binary-src.txt", b"\xff\xfe\x00 not utf-8 \x80\x81")
    write(ctx.raw / "assets" / "figure-src.pdf", b"%PDF-1.4 bytes")
    write(tmp_path / "secret.md", SOURCE_EN)
    refs = [
        "raw/articles/text-src.md",
        "raw/articles/binary-src.txt",
        "raw/assets/figure-src.pdf",
        "raw/articles/gone-src.md",
        "https://example.com/post",
        "raw/../secret.md",
    ]
    write(ctx.wiki / "concepts" / "refs.md", page_text(TWO, refs))
    fs_calls.clear()

    result = probe.run(ctx)

    m = metrics(result)
    assert refs_counts(m) == dict.fromkeys(REF_KINDS, 1)
    assert m["refs_total"] == 6
    assert not [c for c in fs_calls if "secret" in c[1] or "example.com" in c[1]]
    # The wrappers see the probe's own calls, so the check above is not vacuous.
    assert ("open", str(ctx.raw / "articles" / "text-src.md")) in fs_calls
    assert [c for c in fs_calls if c[1] == str(ctx.raw / "articles" / "gone-src.md")]


@pytest.mark.parametrize(
    "ref",
    [
        "raw/../secret.md",
        "raw/sub/../../secret.md",
        "../secret.md",
        "secret.md",
        "wiki/secret.md",
        "raw/..\\secret.md",
        "ABSOLUTE",
        42,
    ],
    ids=[
        "dotdot",
        "nested-dotdot",
        "no-raw-prefix",
        "bare",
        "other-root",
        "backslash",
        "abs",
        "int",
    ],
)
def test_ref_outside_raw_is_counted_outside_without_a_file_system_call(
    probe, tmp_path, fs_calls, ref
):
    ctx = make_ctx(tmp_path)
    write(tmp_path / "secret.md", SOURCE_EN)
    write(ctx.wiki / "secret.md", SOURCE_EN)
    if ref == "ABSOLUTE":
        ref = "raw/" + (tmp_path / "secret.md").as_posix()
    write(ctx.wiki / "concepts" / "out.md", page_text(TWO, [ref]))
    fs_calls.clear()

    result = probe.run(ctx)

    m = metrics(result)
    assert refs_counts(m) == {**dict.fromkeys(REF_KINDS, 0), "outside": 1}
    assert m["refs_total"] == 1
    assert not [c for c in fs_calls if "secret" in c[1]]


@pytest.mark.parametrize(
    "ref", ["http://example.com/a.md", "https://example.com/b"], ids=["http", "https"]
)
def test_url_ref_is_counted_url_without_a_file_system_call(probe, tmp_path, fs_calls, ref):
    ctx = make_ctx(tmp_path)
    write(ctx.wiki / "concepts" / "url.md", page_text(TWO, [ref]))
    fs_calls.clear()

    result = probe.run(ctx)

    assert refs_counts(metrics(result)) == {**dict.fromkeys(REF_KINDS, 0), "url": 1}
    assert not [c for c in fs_calls if "example.com" in c[1]]


@pytest.mark.parametrize("suffix", [".md", ".txt", ".vtt"])
def test_utf8_file_with_a_text_suffix_is_a_text_ref(probe, tmp_path, suffix):
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "articles" / f"src{suffix}", SOURCE_EN)
    write(ctx.wiki / "concepts" / "t.md", page_text(TWO, [f"raw/articles/src{suffix}"]))

    result = probe.run(ctx)

    assert refs_counts(metrics(result)) == {**dict.fromkeys(REF_KINDS, 0), "text": 1}
    assert metrics(result)["band_high"] == 2


@pytest.mark.parametrize("name", ["src.pdf", "src.png", "README"])
def test_regular_file_with_another_suffix_is_non_text_and_is_not_read(
    probe, tmp_path, fs_calls, name
):
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "assets" / name, SOURCE_EN)
    write(ctx.wiki / "concepts" / "n.md", page_text(TWO, [f"raw/assets/{name}"]))
    fs_calls.clear()

    result = probe.run(ctx)

    assert refs_counts(metrics(result)) == {**dict.fromkeys(REF_KINDS, 0), "non_text": 1}
    assert metrics(result)["sentences_no_text_source"] == 2
    assert metrics(result)["pages_no_text_source"] == 1
    touched = {kind for kind, path in fs_calls if path == str(ctx.raw / "assets" / name)}
    assert touched and "open" not in touched


@pytest.mark.parametrize("ref", ["raw/articles/gone.md", "raw/articles/folder.md"])
def test_ref_with_no_regular_file_is_missing(probe, tmp_path, ref):
    ctx = make_ctx(tmp_path)
    (ctx.raw / "articles" / "folder.md").mkdir(parents=True)
    write(ctx.wiki / "concepts" / "m.md", page_text(TWO, [ref]))

    result = probe.run(ctx)

    assert refs_counts(metrics(result)) == {**dict.fromkeys(REF_KINDS, 0), "missing": 1}


def test_text_suffix_that_does_not_decode_as_utf8_is_undecodable(probe, tmp_path):
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "articles" / "latin.txt", "café notes".encode("latin-1"))
    write(ctx.wiki / "concepts" / "u.md", page_text(TWO, ["raw/articles/latin.txt"]))

    result = probe.run(ctx)

    assert refs_counts(metrics(result)) == {**dict.fromkeys(REF_KINDS, 0), "undecodable": 1}
    assert metrics(result)["pages_no_text_source"] == 1


# -- acceptance 3: body and sentences [R3] -----------------------------------------

EN_BODY = """# Title heading
Intro line one is here. Second sentence follows!
Version 3.5 stays whole here.

```python
x = 1. Not a sentence.
```
| col. | value. |
| --- | --- |
This sentence spans
two lines.
No end mark before a heading
## Middle heading
Does it end here? Yes it does.
## Evidence Trail
- 2026-01-01: trail entry one. Trail entry two.
## After
Final words after the trail."""

EN_SENTENCES = [
    "Intro line one is here.",
    "Second sentence follows!",
    "Version 3.5 stays whole here.",
    "This sentence spans\ntwo lines.",
    "No end mark before a heading",
    "Does it end here?",
    "Yes it does.",
    "Final words after the trail.",
]

ZH_BODY = """# 标题。
知识库把原始资料编译成维基页面。每个页面都列出来源！这样可以追溯吗？
```text
代码里的句子。
```
| 表格。 | 行。 |
结尾没有空格的句子。
## Evidence Trail
- 证据记录的句子。"""

ZH_SENTENCES = [
    "知识库把原始资料编译成维基页面。",
    "每个页面都列出来源！",
    "这样可以追溯吗？",
    "结尾没有空格的句子。",
]


@pytest.mark.parametrize(
    ("body", "expected"), [(EN_BODY, EN_SENTENCES), (ZH_BODY, ZH_SENTENCES)], ids=["en", "zh"]
)
def test_body_yields_the_expected_sentences_with_indexes_and_offsets(probe, body, expected):
    text = page_text(body, ["raw/a.md"])

    found = probe.page_sentences(text)

    assert [(s["index"], s["text"]) for s in found] == list(enumerate(expected))
    assert all(text[s["start"] : s["end"]] == s["text"] for s in found)


def test_offsets_hold_for_a_page_with_crlf_line_ends(probe):
    text = page_text(EN_BODY, ["raw/a.md"]).replace("\n", "\r\n")

    found = probe.page_sentences(text)

    assert [s["text"].replace("\r\n", "\n") for s in found] == EN_SENTENCES
    assert all(text[s["start"] : s["end"]] == s["text"] for s in found)


# -- acceptance 4: short sentences [R4] [R5] ---------------------------------------

S19 = "One two six ten ab."  # five words, so only R4 makes it short
ZH7 = "七个字的短句。"
S20_THREE_WORDS = "Abcdefghijklm nop q."
S20_FIVE_WORDS = "Aaaa bbb ccc ddd ee."
ZH8 = "八个字的中文句。"


def test_short_sentences_are_counted_short_and_in_no_band(probe, tmp_path):
    assert (len(S19), len(ZH7), len(S20_THREE_WORDS), len(S20_FIVE_WORDS), len(ZH8)) == (
        19,
        7,
        20,
        20,
        8,
    )
    ctx = make_ctx(tmp_path)
    every = [S19, ZH7, S20_THREE_WORDS, S20_FIVE_WORDS, ZH8]
    # The source holds every sentence verbatim, so any sentence that reached a band
    # would land in band_high.
    write(ctx.raw / "articles" / "src.md", " ".join(every))
    write(ctx.wiki / "concepts" / "short.md", page_text("\n".join(every), ["raw/articles/src.md"]))
    write(
        ctx.wiki / "concepts" / "nosrc.md",
        page_text("A b c d e here. A much longer sentence with plenty of words.", ["raw/x.md"]),
    )

    result = probe.run(ctx)

    m = metrics(result)
    assert m["sentences_short"] == 4
    assert m["sentences"] == 3
    assert m["sentences_no_text_source"] == 1
    assert (m["band_high"], m["band_mid"], m["band_low"]) == (2, 0, 0)


# -- acceptance 5: containment and bands [R5] [R6] --------------------------------

FOX_SOURCE = "the quick brown fox jumps over the lazy dog near the river bank today"
FOX_COPY = "The quick brown fox jumps over the lazy dog."
NO_SHARE = "Completely different words appear in this sentence only."
HALF = "alpha beta gamma delta epsilon zeta eta theta."
HALF_SOURCE = "alpha beta gamma delta epsilon zeta"
ZH_SOURCE = "知识库把原始资料编译成维基页面并保留来源。"
ZH_COPY = "原始资料编译成维基页面并保留来源。"


@pytest.mark.parametrize(
    ("sentence", "sources", "expected"),
    [
        (FOX_COPY, [FOX_SOURCE], 1.0),
        (NO_SHARE, [FOX_SOURCE], 0.0),
        (HALF, [HALF_SOURCE], 0.5),
        (ZH_COPY, [ZH_SOURCE], 1.0),
        (FOX_COPY, ["unrelated words only", FOX_SOURCE], 1.0),
        ("Alpha beta gamma delta epsilon.", ["alpha beta gamma", "delta epsilon"], 0.0),
        ("Four words only here.", [FOX_SOURCE], None),
    ],
    ids=["copy", "none", "half", "zh-copy", "any-source", "no-cross-file-gram", "too-short"],
)
def test_containment_is_the_share_of_ngrams_found_in_a_source(probe, sentence, sources, expected):
    assert probe.containment(sentence, sources) == expected


def test_band_counts_follow_containment_and_sum_to_sentences_with_a_text_source(probe, tmp_path):
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "a.md", "\n".join([FOX_SOURCE, HALF_SOURCE, ZH_SOURCE]))
    write(
        ctx.wiki / "concepts" / "bands.md",
        page_text(" ".join([FOX_COPY, HALF, NO_SHARE, ZH_COPY]), ["raw/a.md"]),
    )
    write(ctx.wiki / "concepts" / "nosrc.md", page_text(f"{FOX_COPY} {NO_SHARE}", ["raw/no.md"]))

    result = probe.run(ctx)

    m = metrics(result)
    assert set(m) == CONTAINMENT_METRICS
    assert (m["band_high"], m["band_mid"], m["band_low"]) == (2, 1, 1)
    assert m["sentences"] == 6
    assert m["sentences_no_text_source"] == 2
    assert m["pages_no_text_source"] == 1
    assert m["band_high"] + m["band_mid"] + m["band_low"] == (
        m["sentences"] - m["sentences_no_text_source"]
    )


def test_band_edges_are_high_from_0_8_and_mid_from_0_2_using_only_the_pages_sources(
    probe, tmp_path
):
    words = "one two three four five six seven eight nine".split()
    sentence = " ".join(words) + "."  # five word 5-grams
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "eight.md", " ".join(words[:8]))  # four of five grams: 0.8
    write(ctx.raw / "five.md", " ".join(words[:5]))  # one of five grams: 0.2
    write(ctx.wiki / "concepts" / "high.md", page_text(sentence, ["raw/eight.md"]))
    write(ctx.wiki / "concepts" / "mid.md", page_text(sentence, ["raw/five.md"]))
    write(ctx.wiki / "concepts" / "low.md", page_text(sentence, ["raw/other.md"]))
    write(ctx.raw / "other.md", "nothing in common at all")

    result = probe.run(ctx)

    m = metrics(result)
    assert (m["band_high"], m["band_mid"], m["band_low"]) == (1, 1, 1)
    assert m["sentences"] == 3


# -- acceptance 6: templates [R7] --------------------------------------------------


def test_templates_with_a_quote_span_offset_or_char_field_are_counted(probe, tmp_path):
    templates = tmp_path / "tpl"
    write(templates / "quote.yaml", "name: quote\nextract:\n  - title\n  - quote\n")
    write(templates / "claims.yaml", "name: claims\nextract:\n  - title\n  - key_claims\n")
    write(
        templates / "described.yaml",
        'extract:\n  - "evidence (str): a quote with char offsets and a span"\n',
    )
    write(templates / "offsets.yaml", 'extract:\n  - "char_start (int): where it starts"\n')
    write(templates / "mapped.yaml", "extract:\n  - source_span: str\n")
    write(templates / "commented.yaml", "extract:\n  - claims  # a quote and its offset\n")
    write(templates / "prompt.txt", "extract:\n  - quote\n")
    ctx = make_ctx(tmp_path, templates=templates)

    result = probe.run(ctx)

    arm = result["arms"]["templates"]
    assert arm["status"] == "measured"
    assert arm["metrics"] == {"templates_total": 6, "templates_with_claim_span": 3}


# -- acceptance 7: the label sample [R8] -------------------------------------------


def sentence_for(n: int, k: int) -> str:
    return f"Sentence {k} of page {n} carries enough words to count."


def build_sample_wiki(ctx, count: int) -> dict[str, Path]:
    pages = {}
    all_text = []
    for n in range(count):
        pid = f"{'concepts' if n % 2 else 'entities'}/page-{n:02d}"
        sentences = [sentence_for(n, k) for k in range(3)]
        all_text += sentences
        path = ctx.wiki / f"{pid}.md"
        write(path, page_text(" ".join(sentences), ["raw/articles/all.md"]))
        pages[pid] = path
    write(ctx.raw / "articles" / "all.md", "\n".join(all_text))
    return pages


def test_sample_takes_two_rows_from_each_of_the_30_pages_with_smallest_sha(probe, tmp_path):
    ctx = make_ctx(tmp_path)
    pages = build_sample_wiki(ctx, 32)

    result = probe.run(ctx)

    rows = sample_rows(ctx)
    first = (ctx.out / SAMPLE).read_bytes()
    chosen = sorted(pages, key=sha)[:30]
    assert len(rows) == 60
    assert {row["page"] for row in rows} == set(chosen)
    for pid in chosen:
        expected = sorted(sorted(range(3), key=lambda i, pid=pid: sha(f"{pid}:{i}"))[:2])
        assert sorted(r["sentence_index"] for r in rows if r["page"] == pid) == expected
    for row in rows:
        assert set(row) == ROW_FIELDS
        page_file = pages[row["page"]].read_bytes().decode("utf-8")
        n = int(row["page"].rsplit("-", 1)[1])
        assert row["text"] == sentence_for(n, row["sentence_index"])
        assert page_file[row["start"] : row["end"]] == row["text"]
        assert row["sha256"] == sha(row["text"])
        assert (row["band"], row["containment"]) == ("high", 1.0)
        assert row["sources"] == ["raw/articles/all.md"]
    assert (metrics(result)["sample_pages"], metrics(result)["sample_sentences"]) == (30, 60)

    probe.run(ctx)

    assert (ctx.out / SAMPLE).read_bytes() == first


def test_sample_of_a_small_wiki_takes_every_page_with_two_banded_sentences(probe, tmp_path):
    ctx = make_ctx(tmp_path)
    pages = build_sample_wiki(ctx, 3)
    crlf = pages["concepts/page-01"]
    crlf.write_bytes(crlf.read_bytes().replace(b"\n", b"\r\n"))
    write(
        ctx.wiki / "summaries" / "single.md",
        page_text(f"{sentence_for(0, 0)} Too short here.", ["raw/articles/all.md"]),
    )

    result = probe.run(ctx)

    rows = sample_rows(ctx)
    assert len(rows) == 6
    assert {row["page"] for row in rows} == set(pages)
    for row in rows:
        page_file = pages[row["page"]].read_bytes().decode("utf-8")
        assert page_file[row["start"] : row["end"]] == row["text"]
    assert (metrics(result)["sample_pages"], metrics(result)["sample_sentences"]) == (3, 6)


# -- acceptance 8: no pages, and the demo corpus through the runner [R9] [R10] ------


def test_wiki_with_no_page_is_unmeasured_and_writes_no_sample(probe, tmp_path):
    ctx = make_ctx(tmp_path)
    write(ctx.wiki / "index.md", page_text(TWO, ["raw/a.md"]))
    write(ctx.out / SAMPLE, "stale row from an earlier run\n")

    result = probe.run(ctx)

    assert containment_arm(result) == {
        "status": "unmeasured",
        "reason": "no pages",
        "cases": 0,
        "metrics": {},
    }
    assert not (ctx.out / SAMPLE).exists()
    assert result["invariants"] == ["I1"]


def test_runner_on_the_demo_corpus_exits_0_with_invariant_i1(bench):
    wiki = REPO / "demo" / "wiki"
    demo_pages = [
        p for p in wiki.rglob("*.md") if p.is_file() and len(p.relative_to(wiki).parts) > 1
    ]
    templates = list((REPO / "templates").rglob("*.yaml"))

    proc = bench.run(
        "--probe",
        "trace",
        "--probes-dir",
        str(PROBES),
        "--wiki",
        str(REPO / "demo" / "wiki"),
        "--raw",
        str(REPO / "demo" / "raw"),
        "--out",
        str(bench.out),
        defaults=False,
    )

    assert proc.returncode == 0, proc.output
    assert "guarded directory changed" not in proc.output
    record = json.loads((bench.out / "trace.json").read_text(encoding="utf-8"))
    assert record["invariants"] == ["I1"]
    arm = record["arms"]["containment"]
    m = arm["metrics"]
    assert (arm["status"], arm["cases"]) == ("measured", len(demo_pages))
    assert m["band_high"] + m["band_mid"] + m["band_low"] == (
        m["sentences"] - m["sentences_no_text_source"]
    )
    assert record["arms"]["templates"]["metrics"]["templates_total"] == len(templates)
    assert (bench.out / SAMPLE).is_file()
