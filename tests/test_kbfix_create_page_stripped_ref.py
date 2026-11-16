"""T0-KBFIX-CREATEREF (#185): `kb_create_page` refuses a `source_refs` entry holding a
character the frontmatter writer deletes.

`kb_create_page` writes each `source:` entry through `yaml_escape`, which first runs
`yaml_sanitize`; that deletes C0/C1 controls other than TAB, LF and CR, DEL, NEL,
U+2028, U+2029, the BOM and bidi marks. The tool only checks that the cited raw file
exists, so a page cited another name than the file on disk. It now returns an
`Error:` string for such an entry and writes nothing.

Every case uses a real file. Windows file names cannot hold C0 controls or TAB, so
those cases run on POSIX only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import frontmatter
import pytest

from kb.mcp import quality
from kb.utils.text import yaml_sanitize

_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows file names cannot hold C0 controls or TAB"
)

_DELETED_CHARS = [
    pytest.param("\x7f", id="del"),
    pytest.param("\x85", id="nel"),
    pytest.param(" ", id="line-separator"),
    pytest.param(" ", id="paragraph-separator"),
    pytest.param("﻿", id="bom"),
    pytest.param("‮", id="rlo"),
    pytest.param("⁦", id="lri"),
    pytest.param("\x01", id="soh", marks=_POSIX_ONLY),
    pytest.param("\x0b", id="vt", marks=_POSIX_ONLY),
    pytest.param("\x1f", id="us", marks=_POSIX_ONLY),
]

_PAGE_ID = "concepts/probe"


def _raw(root: Path, name: str) -> str:
    (root / "raw" / "articles" / name).write_bytes(f"Source {name!r}.\n".encode())
    return f"raw/articles/{name}"


def _create(source_refs: str) -> str:
    return quality.kb_create_page(_PAGE_ID, "Probe", "Body.\n", "concept", "stated", source_refs)


def _snapshot(root: Path) -> dict[str, bytes]:
    """Every file under ``root`` by its relative path, with its bytes."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _assert_refused(result: str, ref: str) -> None:
    assert result.startswith("Error:")
    assert "frontmatter cannot keep" in result
    assert repr(ref) in result
    assert yaml_sanitize(result) == result


@pytest.mark.parametrize("char", _DELETED_CHARS)
def test_create_page_refuses_an_entry_holding_a_character_the_frontmatter_deletes(
    tmp_kb_env: Path, char: str
) -> None:
    ref = _raw(tmp_kb_env, f"b{char}.md")
    before = _snapshot(tmp_kb_env)

    result = _create(ref)

    _assert_refused(result, ref)
    assert _snapshot(tmp_kb_env) == before


def test_create_page_refuses_a_bad_entry_after_a_valid_one(tmp_kb_env: Path) -> None:
    good = _raw(tmp_kb_env, "a.md")
    bad = _raw(tmp_kb_env, "b\x85.md")
    before = _snapshot(tmp_kb_env)

    result = _create(f"{good},{bad}")

    _assert_refused(result, bad)
    assert _snapshot(tmp_kb_env) == before


@pytest.mark.parametrize(
    ("source_refs", "bad"),
    [
        pytest.param("\x85", "\x85", id="nel-only"),
        pytest.param("raw/articles/a.md, ", " ", id="separator-only-after-valid"),
        pytest.param("raw/articles/b.md\x85", "raw/articles/b.md\x85", id="trailing-nel"),
        pytest.param(" raw/articles/b.md", " raw/articles/b.md", id="leading-separator"),
    ],
)
def test_create_page_refuses_an_entry_the_strip_would_shorten(
    tmp_kb_env: Path, source_refs: str, bad: str
) -> None:
    """R3 F1: `strip()` removes NEL and U+2028 at an entry's ends, so the check runs
    on each entry as given; `b.md` exists, so a stripped entry would cite it."""
    _raw(tmp_kb_env, "a.md")
    _raw(tmp_kb_env, "b.md")
    before = _snapshot(tmp_kb_env)

    result = _create(source_refs)

    _assert_refused(result, bad)
    assert _snapshot(tmp_kb_env) == before


def test_create_page_still_strips_spaces_around_entries(tmp_kb_env: Path) -> None:
    """Control for F1: ordinary spaces around entries are still stripped."""
    first = _raw(tmp_kb_env, "a.md")
    second = _raw(tmp_kb_env, "café.md")

    result = _create(f" {first} , {second} ")

    assert result.startswith("Created:")
    page = tmp_kb_env / "wiki" / f"{_PAGE_ID}.md"
    sources = frontmatter.loads(page.read_bytes().decode("utf-8")).metadata["source"]
    assert sources == [first, second]


@pytest.mark.parametrize(
    "name",
    [pytest.param("café.md", id="non-ascii"), pytest.param("b\t.md", id="tab", marks=_POSIX_ONLY)],
)
def test_create_page_keeps_an_entry_the_frontmatter_can_hold(tmp_kb_env: Path, name: str) -> None:
    """Control: an entry `yaml_sanitize` leaves alone is accepted and kept."""
    ref = _raw(tmp_kb_env, name)

    result = _create(ref)

    assert result.startswith("Created:")
    page = tmp_kb_env / "wiki" / f"{_PAGE_ID}.md"
    sources = frontmatter.loads(page.read_bytes().decode("utf-8")).metadata["source"]
    assert sources == [ref]
