"""Acceptance tests 1-8 of card T1-KBEVAL-TRACE for `bench/knowledge/probes/trace.py`."""

from __future__ import annotations

import builtins
import errno
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
| --- | --- |

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


# -- acceptance 3: R3 blocks recognised by CommonMark and GFM block structure -------
# Each row is (id, body, expected sentences). CommonMark decides only which lines are
# fenced code, heading lines or table rows. Every other rule is R3's literal text:
# split at `.`, `!`, `?` before white space or a line end and at `。！？`, then strip
# white space. A kept line keeps its container markers (`>`, `- `, `1. `) as text.

BLOCK_CASES = [
    # GFM tables: header, delimiter and rows are removed; outer pipes are optional, but
    # the header and the delimiter row each need an unescaped `|`.
    (
        "table-no-outer-pipes",
        "Intro sentence here.\n\na | b\n--- | ---\none. | two.\n\nAfter the table.",
        ["Intro sentence here.", "After the table."],
    ),
    (
        "table-in-blockquote",
        "> | a | b |\n> | --- | --- |\n> | one. | two. |\n\nAfter the table.",
        ["After the table."],
    ),
    (
        "table-in-list-item",
        "- Item text here.\n\n  | a | b |\n  |:--|--:|\n  | x. | y. |\n\nAfter.",
        ["- Item text here.", "After."],
    ),
    (
        "table-row-without-pipes-ends-at-heading",
        "a | b\n-|-\nrow without pipes.\n# Heading\nAfter heading.",
        ["After heading."],
    ),
    (
        "table-ends-at-blank-line",
        "| a |\n| - |\n| x. |\n\nProse after blank.",
        ["Prose after blank."],
    ),
    (
        "pipe-line-without-delimiter-is-prose",
        "| a pipe opens this line. It is prose.\nMore prose here.",
        ["| a pipe opens this line.", "It is prose.", "More prose here."],
    ),
    (
        "cell-count-mismatch-is-prose",
        "a | b\n--- | --- | ---\nText here.",
        ["a | b\n--- | --- | ---\nText here."],
    ),
    (
        "no-pipe-in-either-row-is-prose",
        "This ordinary paragraph should remain here.\n:---\n"
        "Another ordinary sentence should remain here.",
        [
            "This ordinary paragraph should remain here.",
            ":---\nAnother ordinary sentence should remain here.",
        ],
    ),
    (
        "header-without-pipe-is-prose",
        "Plain header line here\n|:---|\nRow text here.",
        ["Plain header line here\n|:---|\nRow text here."],
    ),
    (
        "delimiter-without-pipe-is-prose",
        "| Header cell here\n:---\nRow text here.",
        ["| Header cell here\n:---\nRow text here."],
    ),
    # Setext headings: text and underline are removed.
    (
        "setext-equals",
        "Title of the page\n=================\nBody sentence here.",
        ["Body sentence here."],
    ),
    (
        "setext-dash",
        "Second level title\n---\nBody sentence here.",
        ["Body sentence here."],
    ),
    (
        "setext-two-lines",
        "First title line\nsecond title line\n===\nBody.",
        ["Body."],
    ),
    (
        "setext-in-blockquote",
        "> Quoted title\n> ---\n> Quoted body here.",
        ["> Quoted body here."],
    ),
    (
        "dash-underline-under-a-pipe-line-is-setext",
        "| a |\n---\nBody here.",
        ["Body here."],
    ),
    # A --- line after a blank line, or one that ends a blockquote, is a thematic break:
    # R3 does not exclude it, so it is kept text.
    (
        "thematic-break-after-blank-line",
        "Para one ends here.\n\n---\n\nAfter the break.",
        ["Para one ends here.", "---\n\nAfter the break."],
    ),
    (
        "thematic-break-after-blockquote",
        "> Quoted line here.\n---\nAfter rule.",
        ["> Quoted line here.", "---\nAfter rule."],
    ),
    # Fences.
    (
        "backtick-info-with-backtick-is-inline-code",
        "```inline`code``` opens this prose line. Second sentence follows.",
        ["```inline`code``` opens this prose line.", "Second sentence follows."],
    ),
    (
        "fence-in-blockquote",
        "> ```\n> code line. More.\n> ```\nAfter the quote.",
        ["After the quote."],
    ),
    (
        "fence-in-list-item",
        "- Item text here.\n\n  ```\n  code line. More code.\n  ```\n- Next item here.",
        ["- Item text here.", "- Next item here."],
    ),
    (
        "unclosed-fence-ends-with-its-blockquote",
        "> ```\n> code never closed.\n\nProse after the quote.",
        ["Prose after the quote."],
    ),
    (
        "unclosed-fence-ends-with-its-list-item",
        "- ```\n  code never closed.\n\nProse after the list.",
        ["Prose after the list."],
    ),
    (
        "closing-fence-same-character-at-least-as-long",
        "````\ncode.\n```\n~~~~\nstill code.\n````\nAfter.",
        ["After."],
    ),
    (
        "closing-fence-with-info-is-content",
        "```\ncode.\n``` not closing\nstill code.\n```\nAfter.",
        ["After."],
    ),
    (
        "fence-indented-four-is-not-a-fence",
        "Para here.\n\n    ```\n    indented code line.\n\nAfter.",
        ["Para here.", "```\n    indented code line.", "After."],
    ),
    # Tabs advance to the next multiple of 4 columns; the part of a tab a container
    # marker does not consume is indentation (CommonMark 0.31.2, Tabs).
    (
        "tab-after-blockquote-marker-is-indent",
        ">\t  ```\n>   This ordinary sentence has enough words to count.\n>   ```",
        [">\t  ```\n>   This ordinary sentence has enough words to count."],
    ),
    (
        "tab-after-list-marker-is-indent",
        "-\t  ```\n  Item sentence has enough words to count.\n  ```",
        ["-\t  ```\n  Item sentence has enough words to count."],
    ),
    (
        "fence-in-a-second-ordered-item",
        "1. First item text.\n2. ```\n   code line. More.\n   ```\nAfter.",
        ["1.", "First item text.", "After."],
    ),
    (
        "tab-indented-fence-in-list-item",
        "-\tItem text here.\n\n\t```\n\tcode line.\n\t```\nAfter.",
        ["-\tItem text here.", "After."],
    ),
    # ATX headings inside containers; four spaces of indent is not a heading.
    (
        "atx-in-blockquote-and-list-item",
        "> # Quoted heading\n> Quoted body here.\n\n- ## Item heading\n  Item body here.",
        ["> Quoted body here.", "Item body here."],
    ),
    (
        "atx-indented-four-is-text",
        "Para one here.\n    # not a heading line.",
        ["Para one here.", "# not a heading line."],
    ),
    # Evidence Trail: from the line `## Evidence Trail` exactly to the next `## ` ATX
    # heading. A `## ` line inside a fenced block is not a heading, so it ends nothing.
    (
        "trail-starts-only-at-the-exact-line",
        "Body one here.\n## Evidence Trail ##\n- entry one.\n## Next\nBody two here.",
        ["Body one here.", "- entry one.", "Body two here."],
    ),
    (
        "trail-ends-at-a-level-two-atx-heading-with-closing-hashes",
        "Body one here.\n## Evidence Trail\n- entry one.\n## Next ##\nBody two here.",
        ["Body one here.", "Body two here."],
    ),
    (
        "trail-heading-inside-fence-does-not-end-it",
        "Body one here.\n## Evidence Trail\n```\n## not a heading\n```\n- entry.\n## Next\n"
        "Body two here.",
        ["Body one here.", "Body two here."],
    ),
    (
        "trail-not-ended-by-setext-or-level-three",
        "Body one here.\n## Evidence Trail\n- entry one.\n\nNext section\n---\n"
        "Final sentence is excluded.\n### Sub\nAlso excluded here.",
        ["Body one here."],
    ),
    (
        "trail-line-inside-a-fence-starts-the-trail",
        "Body one here.\n```\n## Evidence Trail\n```\nAfter the fence.\n## Next\nBody two here.",
        ["Body one here.", "Body two here."],
    ),
    # Attempt 4: an empty list item ends at a blank line, list-marker digits are ASCII
    # only, and the three table cases the markdown-it-py differential found.
    (
        "empty-item-ends-at-a-blank-line",
        "-\n\n  ```\nFirst fenced sentence contains enough words to count.\n"
        "Second fenced sentence contains enough words to count.\n  ```\n"
        "Ordinary body sentence should remain visible.",
        ["-", "Ordinary body sentence should remain visible."],
    ),
    (
        "non-ascii-digit-is-not-a-list-marker",
        "١. ```\n   First sentence after the marker has enough words.\n"
        "   Second sentence after the marker has enough words.",
        [
            "١.",
            "```\n   First sentence after the marker has enough words.",
            "Second sentence after the marker has enough words.",
        ],
    ),
    (
        "ideographic-space-line-is-not-blank",
        "Title line here\n　\n===\nBody sentence here.",
        ["Body sentence here."],
    ),
    (
        "line-indented-four-ends-a-table",
        "a | b\n--- | ---\nrow one. | two.\n    Indented code line here.\nAfter.",
        ["Indented code line here.", "After."],
    ),
    (
        "lazy-line-is-not-a-table-header",
        "> Quoted paragraph line.\na | b\n> --- | ---\n> row. | row.",
        ["> Quoted paragraph line.", "a | b\n> --- | ---\n> row.", "| row."],
    ),
    (
        "line-indented-four-is-not-a-table-header",
        "Para line one here.\n    a | b\n--- | ---\nAfter.",
        ["Para line one here.", "a | b\n--- | ---\nAfter."],
    ),
    # R3 sentence rule, literally: a list marker's period before a space ends a piece,
    # and container markers stay in the kept text.
    (
        "ordered-list-markers",
        "1. First item text.\n2. Second item text.",
        ["1.", "First item text.", "2.", "Second item text."],
    ),
    (
        "list-marker-period-inside-a-sentence",
        "1. First item\n2. Second item text.",
        ["1.", "First item\n2.", "Second item text."],
    ),
    (
        "quoted-sentence-over-two-lines",
        "> This quoted sentence\n> spans two lines.",
        ["> This quoted sentence\n> spans two lines."],
    ),
]


@pytest.mark.parametrize(
    ("body", "expected"), [c[1:] for c in BLOCK_CASES], ids=[c[0] for c in BLOCK_CASES]
)
def test_block_constructs_are_recognised_by_commonmark_structure(probe, body, expected):
    lf = page_text(body, ["raw/a.md"])
    for text in (lf, lf.replace("\n", "\r\n")):
        found = probe.page_sentences(text)

        assert [s["text"].replace("\r\n", "\n") for s in found] == expected
        assert [s["index"] for s in found] == list(range(len(expected)))
        assert all(text[s["start"] : s["end"]] == s["text"] for s in found)


# -- attempt 2: frontmatter that fails in a YAML constructor [R1] --------------------


def outcome(fn, *args):
    """Return (result, exception) so an unexpected exception fails on an assertion."""
    try:
        return fn(*args), None
    except Exception as exc:
        return None, exc


@pytest.mark.parametrize("value", ["2026-02-30", "2026-13-01"])
def test_frontmatter_rejected_by_a_yaml_constructor_is_unparsed_and_other_pages_complete(
    probe, tmp_path, value
):
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "articles" / "src.md", SOURCE_EN)
    write(ctx.wiki / "concepts" / "bad-date.md", f"---\nupdated: {value}\n---\n{TWO}\n")
    write(ctx.wiki / "concepts" / "good.md", page_text(TWO, ["raw/articles/src.md"]))

    result, error = outcome(probe.run, ctx)

    assert error is None
    assert containment_arm(result)["cases"] == 2
    assert metrics(result)["pages_unparsed"] == 1
    assert metrics(result)["band_high"] == 2


def test_template_rejected_by_a_yaml_constructor_is_counted_without_a_claim_span(probe, tmp_path):
    templates = tmp_path / "tpl"
    write(templates / "bad.yaml", "updated: 2026-02-30\nextract:\n  - quote\n")
    write(templates / "good.yaml", "extract:\n  - quote\n")
    ctx = make_ctx(tmp_path, templates=templates)

    result, error = outcome(probe.run, ctx)

    assert error is None
    assert result["arms"]["templates"]["metrics"] == {
        "templates_total": 2,
        "templates_with_claim_span": 1,
    }


# -- attempt 2: an unreadable source is not a missing source [R2] [R6] -----------------


def source_ctx(tmp_path: Path) -> tuple[SimpleNamespace, Path]:
    ctx = make_ctx(tmp_path)
    target = ctx.raw / "articles" / "locked.md"
    write(target, SOURCE_EN)
    write(ctx.wiki / "concepts" / "p.md", page_text(TWO, ["raw/articles/locked.md"]))
    return ctx, target


def test_permission_error_at_stat_propagates(probe, tmp_path, monkeypatch):
    ctx, target = source_ctx(tmp_path)
    real_stat = Path.stat

    def stat(self, *args, **kwargs):
        if str(self) == str(target):
            raise PermissionError(errno.EACCES, "Permission denied", str(self))
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)

    _, error = outcome(probe.run, ctx)

    assert isinstance(error, PermissionError)


def test_permission_error_at_open_propagates(probe, tmp_path, monkeypatch):
    ctx, target = source_ctx(tmp_path)
    real_open = builtins.open

    def fake_open(file, *args, **kwargs):
        if str(file) == str(target):
            raise PermissionError(errno.EACCES, "Permission denied", str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)

    _, error = outcome(probe.run, ctx)

    assert isinstance(error, PermissionError)


def test_io_error_during_read_propagates(probe, tmp_path, monkeypatch):
    ctx, target = source_ctx(tmp_path)
    real_open = builtins.open

    class FailingRead:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()
            return False

        def read(self, *args, **kwargs):
            raise OSError(errno.EIO, "Input/output error", str(target))

    def fake_open(file, *args, **kwargs):
        handle = real_open(file, *args, **kwargs)
        return FailingRead(handle) if str(file) == str(target) else handle

    monkeypatch.setattr(builtins, "open", fake_open)

    _, error = outcome(probe.run, ctx)

    assert isinstance(error, OSError) and error.errno == errno.EIO


def test_path_through_a_regular_file_is_missing(probe, tmp_path):
    ctx = make_ctx(tmp_path)
    write(ctx.raw / "articles" / "file.md", SOURCE_EN)
    write(ctx.wiki / "concepts" / "p.md", page_text(TWO, ["raw/articles/file.md/inner.md"]))

    result, error = outcome(probe.run, ctx)

    assert error is None
    assert refs_counts(metrics(result)) == {**dict.fromkeys(REF_KINDS, 0), "missing": 1}


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


# -- attempt 4: block recognition seen through the sample [R3] [R8] -----------------

FENCED_ONE = "First fenced sentence contains enough words to count."
FENCED_TWO = "Second fenced sentence contains enough words to count."
LEADING = "Leading body sentence has enough words to count here."
ORDINARY = "Ordinary body sentence should remain visible."
AFTER_ONE = "First sentence after the marker has enough words."
AFTER_TWO = "Second sentence after the marker has enough words."


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            f"{LEADING}\n\n-\n\n  ```\n{FENCED_ONE}\n{FENCED_TWO}\n  ```\n{ORDINARY}",
            [LEADING, ORDINARY],
        ),
        (
            f"١. ```\n   {AFTER_ONE}\n   {AFTER_TWO}",
            [f"```\n   {AFTER_ONE}", AFTER_TWO],
        ),
    ],
    ids=["empty-item-then-blank-line", "arabic-indic-digit-marker"],
)
def test_sample_holds_the_sentences_commonmark_keeps(probe, tmp_path, body, expected):
    ctx = make_ctx(tmp_path)
    write(
        ctx.raw / "src.md",
        "\n".join([LEADING, FENCED_ONE, FENCED_TWO, ORDINARY, AFTER_ONE, AFTER_TWO]),
    )
    page = ctx.wiki / "concepts" / "blocks.md"
    write(page, page_text(body, ["raw/src.md"]))

    result = probe.run(ctx)

    rows = sample_rows(ctx)
    page_file = page.read_bytes().decode("utf-8")
    assert [row["text"] for row in rows] == expected
    assert all(page_file[row["start"] : row["end"]] == row["text"] for row in rows)
    assert metrics(result)["sentences"] == 2


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
