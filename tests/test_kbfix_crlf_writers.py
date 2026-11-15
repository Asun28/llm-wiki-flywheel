"""T1-KBFIX-CRLFWRITERS (#175, part 2): re-ingest, evidence appends and
`kb lint --fix` write a CRLF page back with its own line ends.

Fixture pages are written as bytes: `write_text` on Windows would turn every
"\\n" into "\\r\\n".
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kb.ingest.evidence import SENTINEL, append_evidence_trail
from kb.ingest.pipeline import _update_existing_page, _update_existing_page_body
from kb.lint.checks.dead_links import fix_dead_links

_CRLF = "\r\n"
_LF = "\n"
_NEW_SOURCE = "raw/articles/b.md"
_OLD_MTIME_NS = 1_600_000_000_000_000_000

_FRONTMATTER = [
    "---",
    'title: "Bread"',
    "source:",
    '  - "raw/articles/a.md"',
    "type: entity",
    "confidence: stated",
    "---",
]


def _page(nl: str, lines: list[str]) -> bytes:
    """A page whose lines all end in ``nl``."""
    return (nl.join(lines) + nl).encode("utf-8")


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _all_crlf(data: bytes) -> bool:
    """Every LF is preceded by CR, and no lone CR is left."""
    return data.count(b"\n") == data.count(b"\r\n") and b"\r" not in data.replace(b"\r\n", b"")


def _to_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _lf_copy(path: Path) -> Path:
    """The LF twin of a CRLF fixture page, next to it under its own directory."""
    twin = path.parent.parent / "lf-copy" / path.name
    return _write(twin, _to_lf(path.read_bytes()))


# --- Acceptance 1 [R1] [R2] -------------------------------------------------

_REINGEST_LINES = [
    "---",
    'title: "Bread"',
    "source:",
    '  - "raw/articles/a.md"',
    "created: 2026-01-01",
    "updated: 2026-01-01",
    "type: entity",
    "confidence: stated",
    "---",
    "",
    "# Bread",
    "",
    "## Context",
    "",
    "Bread is baked.",
    "",
    "## References",
    "",
    "- Mentioned in raw/articles/a.md",
    "",
    "## Evidence Trail",
    SENTINEL,
    "- 2026-01-01 | raw/articles/a.md | Created from source",
]


def test_reingest_with_context_keeps_crlf_and_matches_lf_copy(tmp_path):
    crlf_page = _write(tmp_path / "crlf" / "bread.md", _page(_CRLF, _REINGEST_LINES))
    lf_page = _lf_copy(crlf_page)
    ctx = "## Context\n\nBread rises overnight."

    _update_existing_page(crlf_page, _NEW_SOURCE, ctx=ctx)
    _update_existing_page(lf_page, _NEW_SOURCE, ctx=ctx)

    written = crlf_page.read_bytes()
    assert _all_crlf(written)
    assert _to_lf(written) == lf_page.read_bytes()
    text = written.decode("utf-8")
    assert f'  - "{_NEW_SOURCE}"\r\n' in text
    assert f"- Mentioned in {_NEW_SOURCE}\r\n" in text
    assert f"### From `{_NEW_SOURCE}`\r\n\r\nBread rises overnight.\r\n" in text
    assert f"| {_NEW_SOURCE} | Mentioned in new source" in text


# --- Acceptance 2 [R1] ------------------------------------------------------


@pytest.mark.parametrize(
    "references",
    [[], ["## References   ", "", "- Mentioned in raw/articles/a.md"]],
    ids=["no-references", "references-header-not-matched"],
)
def test_fresh_references_block_keeps_crlf(tmp_path, references):
    lines = [*_FRONTMATTER, "", "# Bread", "", "Bread is baked.", *([""] + references)]
    page = _write(tmp_path / "crlf" / "bread.md", _page(_CRLF, lines))
    lf_page = _lf_copy(page)

    assert _update_existing_page_body(page_path=page, source_ref=_NEW_SOURCE) is True
    assert _update_existing_page_body(page_path=lf_page, source_ref=_NEW_SOURCE) is True

    written = page.read_bytes()
    assert _all_crlf(written)
    assert _to_lf(written) == lf_page.read_bytes()
    assert f"## References\r\n\r\n- Mentioned in {_NEW_SOURCE}\r\n".encode() in written


def test_context_inserted_before_references_keeps_crlf(tmp_path):
    lines = [
        *_FRONTMATTER,
        "",
        "# Bread",
        "",
        "## References",
        "",
        "- Mentioned in raw/articles/a.md",
    ]
    page = _write(tmp_path / "crlf" / "bread.md", _page(_CRLF, lines))
    lf_page = _lf_copy(page)
    ctx = "## Context\n\nBread rises overnight."

    _update_existing_page_body(page_path=page, source_ref=_NEW_SOURCE, ctx=ctx)
    _update_existing_page_body(page_path=lf_page, source_ref=_NEW_SOURCE, ctx=ctx)

    written = page.read_bytes()
    assert _all_crlf(written)
    assert _to_lf(written) == lf_page.read_bytes()
    assert b"## Context\r\n\r\nBread rises overnight.\r\n\r\n## References\r\n" in written


# --- Acceptance 3 [R2] ------------------------------------------------------

_EVIDENCE_BRANCHES = {
    "sentinel-in-section": [
        "## Evidence Trail",
        SENTINEL,
        "- 2026-01-01 | raw/articles/a.md | Created from source",
        "",
        "## Notes",
        "",
        "Kept.",
    ],
    "header-without-sentinel": [
        "## Evidence Trail",
        "- 2026-01-01 | raw/articles/a.md | Created from source",
        "",
        "## Notes",
        "",
        "Kept.",
    ],
    "no-header": ["## Notes", "", "Kept."],
}


@pytest.mark.parametrize("branch", list(_EVIDENCE_BRANCHES))
def test_evidence_append_keeps_crlf_in_each_branch(tmp_path, branch):
    lines = [*_FRONTMATTER, "", "# Bread", "", *_EVIDENCE_BRANCHES[branch]]
    page = _write(tmp_path / "crlf" / "bread.md", _page(_CRLF, lines))
    lf_page = _lf_copy(page)

    append_evidence_trail(page, _NEW_SOURCE, "Mentioned in new source", "2026-01-02")
    append_evidence_trail(lf_page, _NEW_SOURCE, "Mentioned in new source", "2026-01-02")

    written = page.read_bytes()
    assert _all_crlf(written)
    assert _to_lf(written) == lf_page.read_bytes()
    assert f"{SENTINEL}\r\n- 2026-01-02 | {_NEW_SOURCE} | Mentioned in new source\r\n".encode() in (
        written
    )


# --- Acceptance 4 [R3] ------------------------------------------------------


def _dead_link_lines() -> list[str]:
    filler = [f"Line {i}." for i in range(19)]
    return [
        *_FRONTMATTER,
        "",
        "# Bread",
        "",
        "See [[concepts/missing-one]] here.",
        *filler,
        "Also [[concepts/missing-two|Two]] there.",
        "",
        "```",
        "[[concepts/missing-one]] stays in code.",
        "```",
    ]


def test_dead_links_fix_keeps_crlf_and_leaves_clean_page_unwritten(tmp_wiki):
    page = _write(tmp_wiki / "entities" / "bread.md", _page(_CRLF, _dead_link_lines()))
    clean_bytes = _page(_CRLF, [*_FRONTMATTER, "", "# Salt", "", "Goes in [[entities/bread]]."])
    clean = _write(tmp_wiki / "entities" / "salt.md", clean_bytes)
    os.utime(clean, ns=(_OLD_MTIME_NS, _OLD_MTIME_NS))

    fixes = fix_dead_links(tmp_wiki)

    assert sorted(f["target"] for f in fixes) == ["concepts/missing-one", "concepts/missing-two"]
    expected = _dead_link_lines()
    expected[expected.index("See [[concepts/missing-one]] here.")] = "See missing-one here."
    expected[expected.index("Also [[concepts/missing-two|Two]] there.")] = "Also Two there."
    assert page.read_bytes() == _page(_CRLF, expected)
    assert clean.read_bytes() == clean_bytes
    assert clean.stat().st_mtime_ns == _OLD_MTIME_NS


def test_dead_link_only_inside_code_leaves_crlf_page_unwritten(tmp_wiki):
    lines = [*_FRONTMATTER, "", "# Bread", "", "```", "[[concepts/gone]]", "```"]
    data = _page(_CRLF, lines)
    page = _write(tmp_wiki / "entities" / "bread.md", data)
    os.utime(page, ns=(_OLD_MTIME_NS, _OLD_MTIME_NS))

    fixes = fix_dead_links(
        tmp_wiki, broken_links=[{"source": "entities/bread", "target": "concepts/gone"}]
    )

    assert fixes == []
    assert page.read_bytes() == data
    assert page.stat().st_mtime_ns == _OLD_MTIME_NS


# --- Acceptance 5 [R1] [R2] [R3] [R4] ---------------------------------------

_PLAIN = "Plain line."


def _mixed(lines: list[str]) -> bytes:
    """CRLF on every line except the line equal to ``_PLAIN``, which ends in LF."""
    data = _page(_CRLF, lines)
    return data.replace(f"{_PLAIN}\r\n".encode(), f"{_PLAIN}\n".encode())


_BODY_PAGE = [
    *_FRONTMATTER,
    "",
    "# Bread",
    "",
    _PLAIN,
    "",
    "## Context",
    "",
    "Bread is baked.",
    "",
    "## References",
    "",
    "- Mentioned in raw/articles/a.md",
]
_BODY_EXPECTED = [
    "---",
    'title: "Bread"',
    "source:",
    '  - "raw/articles/a.md"',
    '  - "raw/articles/b.md"',
    "type: entity",
    "confidence: stated",
    "---",
    "",
    "# Bread",
    "",
    _PLAIN,
    "",
    "## Context",
    "",
    "Bread is baked.",
    "### From `raw/articles/b.md`",
    "",
    "Bread rises overnight.",
    "## References",
    "",
    "- Mentioned in raw/articles/a.md",
    "- Mentioned in raw/articles/b.md",
]

_EVIDENCE_PAGE = [*_FRONTMATTER, "", "# Bread", "", _PLAIN, "", *_EVIDENCE_BRANCHES["no-header"]]
_EVIDENCE_EXPECTED = [
    *_EVIDENCE_PAGE,
    "",
    "## Evidence Trail",
    SENTINEL,
    "- 2026-01-02 | raw/articles/b.md | Mentioned in new source",
]

_LINKS_PAGE = [*_FRONTMATTER, "", "# Bread", "", "See [[concepts/gone]] here.", _PLAIN, "End."]
_LINKS_EXPECTED = [*_FRONTMATTER, "", "# Bread", "", "See gone here.", _PLAIN, "End."]


def _run_body(path: Path) -> None:
    _update_existing_page_body(
        page_path=path, source_ref=_NEW_SOURCE, ctx="## Context\n\nBread rises overnight."
    )


def _run_evidence(path: Path) -> None:
    append_evidence_trail(path, _NEW_SOURCE, "Mentioned in new source", "2026-01-02")


def _run_links(path: Path) -> None:
    fix_dead_links(
        path.parent.parent, broken_links=[{"source": "entities/bread", "target": "concepts/gone"}]
    )


_WRITERS = {
    "ingest-body": (_run_body, _BODY_PAGE, _BODY_EXPECTED),
    "evidence": (_run_evidence, _EVIDENCE_PAGE, _EVIDENCE_EXPECTED),
    "dead-links": (_run_links, _LINKS_PAGE, _LINKS_EXPECTED),
}


@pytest.mark.parametrize("writer", list(_WRITERS))
def test_mixed_page_keeps_the_lf_of_an_unchanged_line(tmp_wiki, writer):
    run, page_lines, expected_lines = _WRITERS[writer]
    page = _write(tmp_wiki / "entities" / "bread.md", _mixed(page_lines))

    run(page)

    assert page.read_bytes() == _mixed(expected_lines)


@pytest.mark.parametrize("writer", list(_WRITERS))
def test_lf_page_is_written_with_the_same_bytes_as_before(tmp_wiki, writer):
    run, page_lines, expected_lines = _WRITERS[writer]
    page = _write(tmp_wiki / "entities" / "bread.md", _page(_LF, page_lines))

    run(page)

    assert page.read_bytes() == _page(_LF, expected_lines)
