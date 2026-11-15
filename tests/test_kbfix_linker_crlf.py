"""T0-KBFIX-CRLF (#168): wikilink injection writes a page back with its own line
endings: CRLF, LF and lone CR are kept."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kb.compile.linker import inject_wikilinks, inject_wikilinks_batch
from kb.utils.markdown import FRONTMATTER_RE
from kb.utils.pages import load_all_pages

_TARGET = "concepts/hydration"
_LINK = f"[[{_TARGET}|Hydration]]"
_APIS = ["single", "batch", "batch-pages"]


def _page(nl: str, body_lines: list[str]) -> bytes:
    """A page whose frontmatter and body lines all end in ``nl``."""
    lines = [
        "---",
        'title: "Bread"',
        "source:",
        '  - "raw/articles/a.md"',
        "type: entity",
        "confidence: stated",
        "created: 2026-04-01",
        "updated: 2026-04-01",
        "---",
        "",
        *body_lines,
    ]
    return (nl.join(lines) + nl).encode("utf-8")


def _write(wiki: Path, data: bytes) -> Path:
    # Bytes, not text: write_text on Windows would turn every "\n" into "\r\n".
    path = wiki / "entities" / "bread.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _inject(api: str, wiki: Path, title: str = "Hydration") -> list[str]:
    if api == "single":
        return inject_wikilinks(title, _TARGET, wiki_dir=wiki)
    pages = load_all_pages(wiki) if api == "batch-pages" else None
    return inject_wikilinks_batch([(title, _TARGET)], wiki_dir=wiki, pages=pages)[_TARGET]


# --- Acceptance 1 [R1] -----------------------------------------------------


@pytest.mark.parametrize("nl", ["\r\n", "\n"], ids=["crlf", "lf"])
@pytest.mark.parametrize("api", _APIS)
def test_page_keeps_its_line_endings(tmp_wiki, api, nl):
    path = _write(tmp_wiki, _page(nl, ["## Hydration", "", "Hydration matters."]))
    assert _inject(api, tmp_wiki) == ["entities/bread"]
    assert path.read_bytes() == _page(nl, ["## Hydration", "", f"{_LINK} matters."])


@pytest.mark.parametrize("api", _APIS)
def test_crlf_page_without_a_final_line_end_keeps_its_ends(tmp_wiki, api):
    path = _write(tmp_wiki, _page("\r\n", ["## Hydration", "", "Hydration matters."])[:-2])
    assert _inject(api, tmp_wiki) == ["entities/bread"]
    assert path.read_bytes() == _page("\r\n", ["## Hydration", "", f"{_LINK} matters."])[:-2]


@pytest.mark.parametrize("api", _APIS)
def test_title_spanning_a_crlf_line_end_keeps_the_other_ends(tmp_wiki, api):
    # The link replaces "Hydration<CRLF>matters", so that one line end goes and
    # every other line end of the page stays CRLF.
    path = _write(tmp_wiki, _page("\r\n", ["## Notes", "", "Hydration", "matters here.", "End."]))
    assert _inject(api, tmp_wiki, "Hydration\nmatters") == ["entities/bread"]
    linked = f"[[{_TARGET}|Hydration matters]] here."
    assert path.read_bytes() == _page("\r\n", ["## Notes", "", linked, "End."])


# --- Acceptance 2 [R1] -----------------------------------------------------

_MIXED_BODY = "## Hydration\r\n\nIntro.\r\nHydration matters.\nLast line.\r\n"


@pytest.mark.parametrize("api", _APIS)
def test_mixed_crlf_and_lf_endings_are_kept(tmp_wiki, api):
    head = _page("\r\n", [])
    path = _write(tmp_wiki, head + _MIXED_BODY.encode("utf-8"))
    assert _inject(api, tmp_wiki) == ["entities/bread"]
    expected_body = "## Hydration\r\n\nIntro.\r\n" + f"{_LINK} matters.\nLast line.\r\n"
    assert path.read_bytes() == head + expected_body.encode("utf-8")


@pytest.mark.parametrize("api", _APIS)
def test_lone_cr_endings_are_written_as_lf(tmp_wiki, api):
    # The frontmatter and heading patterns see only LF and CRLF line ends, so a
    # lone CR becomes LF (as Path.read_text did) and the heading stays unlinked.
    path = _write(tmp_wiki, _page("\r", ["## Hydration", "", "Hydration matters."]))
    assert _inject(api, tmp_wiki) == ["entities/bread"]
    assert path.read_bytes() == _page("\n", ["## Hydration", "", f"{_LINK} matters."])


# --- Acceptance 3 [R2] -----------------------------------------------------


# The empty heading "###" holds the title "###" (R3 F1): `_ATX_HEADING_RE`
# needs its `$` right after the hashes, which a kept CR would block.
@pytest.mark.parametrize(
    ("title", "heading"),
    [("Hydration", "## Hydration"), ("###", "###")],
    ids=["heading", "empty-heading"],
)
@pytest.mark.parametrize("api", _APIS)
def test_crlf_page_matching_only_in_a_heading_is_not_written(tmp_wiki, api, title, heading):
    before = _page("\r\n", [heading, "", "Bread is baked."])
    path = _write(tmp_wiki, before)
    old = os.stat(path).st_mtime_ns - 10_000_000_000
    os.utime(path, ns=(old, old))
    assert _inject(api, tmp_wiki, title) == []
    assert (path.read_bytes(), os.stat(path).st_mtime_ns) == (before, old)


# --- R3 F2: CRLF frontmatter near FRONTMATTER_RE's 10,000-character bound ---

_FILLER = [f"note{i:03d}: {'x' * 30}" for i in range(245)]


def _long_frontmatter_page(nl: str, body_line: str) -> bytes:
    lines = ["---", 'title: "Hydration"', *_FILLER, "---", "", "## Hydration", "", body_line]
    return (nl.join(lines) + nl).encode("utf-8")


@pytest.mark.parametrize("api", _APIS)
def test_crlf_frontmatter_near_the_bound_stays_unlinked(tmp_wiki, api):
    before = _long_frontmatter_page("\r\n", "Hydration matters.")
    # The block fits the bound with LF line ends and exceeds it with CRLF ones.
    assert FRONTMATTER_RE.match(before.decode("utf-8").replace("\r\n", "\n"))
    assert not FRONTMATTER_RE.match(before.decode("utf-8"))
    path = _write(tmp_wiki, before)
    assert _inject(api, tmp_wiki) == ["entities/bread"]
    assert path.read_bytes() == _long_frontmatter_page("\r\n", f"{_LINK} matters.")
