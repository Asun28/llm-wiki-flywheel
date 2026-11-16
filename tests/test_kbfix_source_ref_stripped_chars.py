"""T0-KBFIX-STRIPREF (#183): ingest refuses a source reference holding a character
the frontmatter writer deletes.

`_update_existing_page_body` writes a page's new `source:` entry through
`yaml_escape`, which first runs `yaml_sanitize`; that deletes C0/C1 controls other
than TAB, LF and CR, DEL, NEL, U+2028, U+2029, the BOM and bidi marks. A re-ingest
that added such a source to an existing page therefore cited a file that does not
exist. `ingest_source` now refuses such a reference before it writes any file.

Every case uses a real file. Windows file names cannot hold C0 controls or TAB, so
those cases run on POSIX only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import frontmatter
import pytest

from kb.ingest import pipeline as pipeline_mod
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


def _extraction(title: str) -> dict:
    return {
        "title": title,
        "summary": f"Source {title} for the stripped-character reference tests.",
        "entities_mentioned": ["Bread"],
        "concepts_mentioned": [],
        "key_points": ["One point."],
    }


def _seed_indexes(root: Path) -> None:
    wiki = root / "wiki"
    (wiki / "index.md").write_bytes(
        b"# Index\n\n## Summaries\n\n## Entities\n\n## Concepts\n\n"
        b"## Comparisons\n\n## Synthesis\n\n"
    )
    (wiki / "_sources.md").write_bytes(b"# Sources\n\n")
    (wiki / "log.md").write_bytes(b"# Log\n\n")


def _raw(root: Path, name: str) -> Path:
    raw = root / "raw" / "articles" / name
    raw.write_bytes(f"# Source\n\nBread, from {name!r}.\n".encode())
    return raw


def _ingest(root: Path, raw: Path, title: str) -> dict:
    return pipeline_mod.ingest_source(
        raw,
        source_type="article",
        extraction=_extraction(title),
        wiki_dir=root / "wiki",
        raw_dir=root / "raw",
        _skip_vector_rebuild=True,
    )


def _snapshot(root: Path) -> dict[str, bytes]:
    """Every file under ``root`` by its relative path, with its bytes."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.mark.parametrize("char", _DELETED_CHARS)
def test_ingest_refuses_a_reference_holding_a_character_the_frontmatter_deletes(
    tmp_kb_env: Path, char: str
) -> None:
    _seed_indexes(tmp_kb_env)
    raw = _raw(tmp_kb_env, f"b{char}.md")
    before = _snapshot(tmp_kb_env)

    with pytest.raises(ValueError, match="frontmatter cannot keep") as excinfo:
        _ingest(tmp_kb_env, raw, "Beta")

    message = str(excinfo.value)
    assert repr(f"raw/articles/b{char}.md") in message
    assert yaml_sanitize(message) == message
    assert _snapshot(tmp_kb_env) == before


@pytest.mark.parametrize(
    "name",
    [pytest.param("café.md", id="non-ascii"), pytest.param("b\t.md", id="tab", marks=_POSIX_ONLY)],
)
def test_an_updated_page_keeps_a_reference_the_frontmatter_can_hold(
    tmp_kb_env: Path, name: str
) -> None:
    """Control: a reference `yaml_sanitize` leaves alone is accepted and kept."""
    _seed_indexes(tmp_kb_env)
    _ingest(tmp_kb_env, _raw(tmp_kb_env, "a.md"), "Alpha")

    _ingest(tmp_kb_env, _raw(tmp_kb_env, name), "Beta")

    page = tmp_kb_env / "wiki" / "entities" / "bread.md"
    sources = frontmatter.loads(page.read_bytes().decode("utf-8")).metadata["source"]
    assert f"raw/articles/{name}" in sources
