"""T0-KBFIX-CRREF (#179): ingest refuses a source reference holding a CR or LF.

The reference built from the source path is written into line-oriented files:
the References line of a wiki page and the entry in `wiki/_sources.md`. Neither
can keep a line break inside the reference. The page writer turns a CR into LF
and splits the References line; `_sources.md` splits the entry on its next read,
and a re-ingest then appends a duplicate instead of merging. `ingest_source`
therefore raises `ValueError` before it writes any file.

A Windows file name cannot hold CR or LF, so the cross-platform tests stand in
for that file name by patching `make_source_ref`; the POSIX test uses a real one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from kb.ingest import pipeline as pipeline_mod

_LINE_BREAK_REFS = {
    "lone-cr": "raw/articles/b\r.md",
    "crlf": "raw/articles/b\r\n.md",
    "lf": "raw/articles/b\n.md",
}


def _extraction() -> dict:
    return {
        "title": "Line Break Reference",
        "summary": "A source for the line-break reference tests.",
        "entities_mentioned": [],
        "concepts_mentioned": [],
        "key_points": ["One point."],
    }


def _seed(root: Path, name: str) -> Path:
    wiki = root / "wiki"
    (wiki / "index.md").write_bytes(
        b"# Index\n\n## Summaries\n\n## Entities\n\n## Concepts\n\n"
        b"## Comparisons\n\n## Synthesis\n\n"
    )
    (wiki / "_sources.md").write_bytes(b"# Sources\n\n")
    (wiki / "log.md").write_bytes(b"# Log\n\n")
    raw = root / "raw" / "articles" / name
    raw.write_bytes(b"# B\n\nBody of the source.\n")
    return raw


def _ingest(root: Path, raw: Path) -> dict:
    return pipeline_mod.ingest_source(
        raw,
        source_type="article",
        extraction=_extraction(),
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


@pytest.mark.parametrize("ref", list(_LINE_BREAK_REFS.values()), ids=list(_LINE_BREAK_REFS))
def test_ingest_refuses_a_reference_holding_a_line_break(
    tmp_kb_env: Path, monkeypatch: pytest.MonkeyPatch, ref: str
) -> None:
    raw = _seed(tmp_kb_env, "b.md")
    monkeypatch.setattr(pipeline_mod, "make_source_ref", lambda *args, **kwargs: ref)
    before = _snapshot(tmp_kb_env)

    with pytest.raises(ValueError, match="line break") as excinfo:
        _ingest(tmp_kb_env, raw)

    message = str(excinfo.value)
    assert repr(ref) in message
    assert "\r" not in message and "\n" not in message
    assert _snapshot(tmp_kb_env) == before


@pytest.mark.skipif(sys.platform == "win32", reason="Windows file names cannot hold CR or LF")
@pytest.mark.parametrize("name", ["b\r.md", "b\r\n.md"], ids=["lone-cr", "crlf"])
def test_ingest_refuses_a_posix_file_name_holding_a_line_break(tmp_kb_env: Path, name: str) -> None:
    raw = _seed(tmp_kb_env, name)
    before = _snapshot(tmp_kb_env)

    with pytest.raises(ValueError, match="line break"):
        _ingest(tmp_kb_env, raw)

    assert _snapshot(tmp_kb_env) == before


def test_the_snapshot_sees_the_write_of_an_accepted_reference(
    tmp_kb_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control: the same seam with a reference holding no line break ingests."""
    raw = _seed(tmp_kb_env, "b.md")
    monkeypatch.setattr(
        pipeline_mod, "make_source_ref", lambda *args, **kwargs: "raw/articles/b.md"
    )
    before = _snapshot(tmp_kb_env)

    _ingest(tmp_kb_env, raw)

    added = set(_snapshot(tmp_kb_env)) - set(before)
    assert any(path.startswith("wiki/summaries/") for path in added)
