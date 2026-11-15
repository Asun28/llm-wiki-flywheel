"""T1-KBFIX-FROMHEAD (#161): wikilink injection never edits an ATX heading line,
and ingest writes the ``### From`` source ref as one inline code span."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

from kb.compile.linker import _mask_code_blocks, inject_wikilinks, inject_wikilinks_batch
from kb.ingest.pipeline import _update_existing_page, ingest_source

_FM = (
    '---\ntitle: "Bread"\nsource:\n  - "raw/articles/a.md"\ntype: entity\n'
    "confidence: stated\ncreated: 2026-04-01\nupdated: 2026-04-01\n---\n\n"
)
_TARGET = "concepts/hydration"


def _md() -> MarkdownIt:
    return MarkdownIt("commonmark")


def _heading_code_spans(line: str) -> list[str]:
    """Contents of the code_inline tokens of a markdown line parsed as one heading."""
    tokens = _md().parse(line)
    assert [t.type for t in tokens] == ["heading_open", "inline", "heading_close"], line
    return [c.content for c in tokens[1].children if c.type == "code_inline"]


def _from_heading(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.startswith("### From ")]
    assert len(lines) == 1, lines
    return lines[0]


def _write_page(wiki: Path, body: str, name: str = "bread") -> Path:
    path = wiki / "entities" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((_FM + body).encode("utf-8"))
    return path


def _inject(api: str, wiki: Path) -> list[str]:
    if api == "single":
        return inject_wikilinks("Hydration", _TARGET, wiki_dir=wiki)
    return inject_wikilinks_batch([("Hydration", _TARGET)], wiki_dir=wiki)[_TARGET]


_LINKED_BODY = f"[[{_TARGET}|Hydration]] matters.\n"


# --- Acceptance 1 [R1] -----------------------------------------------------


def test_reingest_writes_from_heading_with_inline_code_ref(tmp_project, monkeypatch):
    data_dir = tmp_project / ".data"
    data_dir.mkdir()
    monkeypatch.setattr("kb.compile.compiler.HASH_MANIFEST", data_dir / "hashes.json")
    wiki, raw = tmp_project / "wiki", tmp_project / "raw"
    for name, claim in (("first", "Acme bakes rye bread."), ("second", "Acme ships sourdough.")):
        raw_path = raw / "articles" / f"{name}.md"
        raw_path.write_text(f"# {name}\n\n{claim}\n", encoding="utf-8")
        ingest_source(
            raw_path,
            "article",
            extraction={
                "title": f"{name.title()} Article",
                "core_argument": claim,
                "key_claims": [claim],
                "entities_mentioned": ["Acme"],
                "concepts_mentioned": [],
            },
            wiki_dir=wiki,
            raw_dir=raw,
            _skip_vector_rebuild=True,
        )
    text = (wiki / "entities" / "acme.md").read_text(encoding="utf-8")
    assert "## Context" in text
    assert _from_heading(text) == "### From `raw/articles/second.md`"


@pytest.mark.parametrize(
    ("ref", "expected_heading"),
    [
        ("raw/articles/b.md", "### From `raw/articles/b.md`"),
        ("raw/articles/a`b.md", "### From `` raw/articles/a`b.md ``"),
        ("raw/articles/a``b.md", "### From ``` raw/articles/a``b.md ```"),
    ],
    ids=["no-backtick", "one-backtick", "two-backticks"],
)
def test_from_heading_ref_is_one_code_span(tmp_wiki, ref, expected_heading):
    page = _write_page(tmp_wiki, "Bread.\n\n## Context\n\nContext from source a.\n")
    _update_existing_page(page, source_ref=ref, verb="Referenced", ctx="Context from b.")
    heading = _from_heading(page.read_text(encoding="utf-8"))
    assert heading == expected_heading
    assert _heading_code_spans(heading) == [ref]


# --- Acceptance 2 [R2] -----------------------------------------------------


@pytest.mark.parametrize("api", ["single", "batch"])
def test_from_heading_kept_while_body_is_linked(tmp_wiki, api):
    heading = "### From raw/articles/high-hydration.md"
    page = _write_page(tmp_wiki, f"{heading}\n\nHydration matters.\n")
    assert _inject(api, tmp_wiki) == ["entities/bread"]
    assert page.read_bytes().decode("utf-8") == _FM + f"{heading}\n\n{_LINKED_BODY}"


@pytest.mark.parametrize("api", ["single", "batch"])
def test_heading_holding_inline_code_is_restored_fully(tmp_wiki, api):
    # The heading carries a code placeholder after code masking; it must be
    # restored as its original text, not as a line with a stale placeholder.
    heading = "## Hydration notes from `raw/articles/high-hydration.md`"
    page = _write_page(tmp_wiki, f"{heading}\n\nHydration matters.\n")
    assert _inject(api, tmp_wiki) == ["entities/bread"]
    assert page.read_bytes().decode("utf-8") == _FM + f"{heading}\n\n{_LINKED_BODY}"


# --- Acceptance 3 [R2] -----------------------------------------------------

_HEADINGS = [
    *(f"{'#' * level} Hydration level {level}" for level in range(1, 7)),
    *(f"{' ' * indent}## Hydration indent {indent}" for indent in range(0, 4)),
    "## Hydration closed ##",
    "#\tHydration after tab",
]


def test_heading_fixtures_are_commonmark_headings():
    for line in _HEADINGS:
        assert _md().parse(line)[0].type == "heading_open", line


@pytest.mark.parametrize("api", ["single", "batch"])
def test_all_atx_heading_forms_stay_byte_identical(tmp_wiki, api):
    headings = "\n\n".join(_HEADINGS)
    page = _write_page(tmp_wiki, f"{headings}\n\nHydration matters.\n")
    assert _inject(api, tmp_wiki) == ["entities/bread"]
    assert page.read_bytes().decode("utf-8") == _FM + f"{headings}\n\n{_LINKED_BODY}"


@pytest.mark.parametrize("api", ["single", "batch"])
def test_hash_without_space_is_not_a_heading(tmp_wiki, api):
    line = "#tag Hydration matters."
    assert _md().parse(line)[0].type == "paragraph_open"
    page = _write_page(tmp_wiki, f"{line}\n")
    assert _inject(api, tmp_wiki) == ["entities/bread"]
    assert page.read_bytes().decode("utf-8") == _FM + f"#tag {_LINKED_BODY}"


# --- Acceptance 4 [R2] -----------------------------------------------------


@pytest.mark.parametrize("api", ["single", "batch"])
def test_page_matching_only_in_headings_is_not_written(tmp_wiki, api):
    page = _write_page(
        tmp_wiki, "# Hydration\n\n### From raw/articles/high-hydration.md\n\nBread only.\n"
    )
    old = os.stat(page).st_mtime_ns - 10_000_000_000
    os.utime(page, ns=(old, old))
    before = page.read_bytes()
    assert _inject(api, tmp_wiki) == []
    assert page.read_bytes() == before
    assert os.stat(page).st_mtime_ns == old


# --- Acceptance 5 [R3] -----------------------------------------------------


def test_mask_code_blocks_does_not_mask_headings():
    sample = (
        "# Hydration\n"
        "Use `water` and [docs](http://x/y) and ![pic](a.png).\n"
        "\n"
        "```py\n# not a heading\n```\n"
        "\n"
        "### From `raw/articles/high-hydration.md`\n"
    )
    text, masked, prefix = _mask_code_blocks(sample)
    assert masked == [
        "`water`",
        "[docs](http://x/y)",
        "![pic](a.png)",
        "```py\n# not a heading\n```",
        "`raw/articles/high-hydration.md`",
    ]
    assert text.replace(prefix, "P") == (
        "# Hydration\n"
        "Use \x00P0\x00 and \x00P1\x00 and \x00P2\x00.\n"
        "\n"
        "\x00P3\x00\n"
        "\n"
        "### From \x00P4\x00\n"
    )
