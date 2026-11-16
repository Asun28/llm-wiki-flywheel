"""T1-KBFIX-CRLFWRITERS (#175, part 2): re-ingest, evidence appends and
`kb lint --fix` write a CRLF page back with its own line ends.

Fixture pages are written as bytes: `write_text` on Windows would turn every
"\\n" into "\\r\\n".
"""

from __future__ import annotations

import datetime
import os
import re
from pathlib import Path

import pytest

from kb.ingest.evidence import SENTINEL, append_evidence_trail
from kb.ingest.pipeline import (
    _process_item_batch,
    _update_existing_page,
    _update_existing_page_body,
)
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


# --- Acceptance 8 [R4] [R5] -------------------------------------------------


class _FixedDate(datetime.date):
    @classmethod
    def today(cls) -> datetime.date:
        return cls(2026, 1, 2)


_CR_PAGE = [
    *_FRONTMATTER,
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

# Inserted text holding a CRLF (extraction field) or a CRLF and a lone CR (direct ctx).
_CR_INPUTS = {
    "extraction": {"name": "Bread", "extraction": {"core_argument": "Bread rises.\r\nBake it."}},
    "direct-ctx": {"ctx": "## Context\n\nBread rises.\r\nBake it.\rCool it."},
}
# What the call wrote on an all-LF page before this card: the evidence append's
# `read_text` turned every CR into LF.
_CR_CONTEXT_LF_BEFORE = {
    "extraction": ["- Bread rises.", "Bake it."],
    "direct-ctx": ["Bread rises.", "Bake it.", "Cool it."],
}


def _cr_expected(inserted: list[str]) -> list[str]:
    return [
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
        "## Context",
        "",
        "Bread is baked.",
        "### From `raw/articles/b.md`",
        "",
        *inserted,
        "## References",
        "",
        "- Mentioned in raw/articles/a.md",
        "- Mentioned in raw/articles/b.md",
        "",
        "## Evidence Trail",
        SENTINEL,
        "- 2026-01-02 | raw/articles/b.md | Mentioned in new source — source reference added",
        "- 2026-01-01 | raw/articles/a.md | Created from source",
    ]


@pytest.mark.parametrize("source", list(_CR_INPUTS))
def test_cr_in_inserted_context_is_written_crlf_on_crlf_page(tmp_path, monkeypatch, source):
    monkeypatch.setattr("kb.ingest.evidence.date", _FixedDate)
    crlf_page = _write(tmp_path / "crlf" / "bread.md", _page(_CRLF, _CR_PAGE))
    lf_page = _lf_copy(crlf_page)

    _update_existing_page(crlf_page, _NEW_SOURCE, **_CR_INPUTS[source])
    _update_existing_page(lf_page, _NEW_SOURCE, **_CR_INPUTS[source])

    written = crlf_page.read_bytes()
    assert b"\r\r" not in written
    assert _all_crlf(written)
    assert len(written.splitlines()) == len(lf_page.read_bytes().splitlines())


@pytest.mark.parametrize("source", list(_CR_INPUTS))
def test_cr_in_inserted_context_on_lf_page_writes_the_bytes_of_before(
    tmp_path, monkeypatch, source
):
    monkeypatch.setattr("kb.ingest.evidence.date", _FixedDate)
    page = _write(tmp_path / "lf" / "bread.md", _page(_LF, _CR_PAGE))

    _update_existing_page(page, _NEW_SOURCE, **_CR_INPUTS[source])

    assert page.read_bytes() == _page(_LF, _cr_expected(_CR_CONTEXT_LF_BEFORE[source]))


_CR_ACTION = "Mentioned\r\nin new source"


def test_cr_in_evidence_action_is_written_crlf_on_crlf_page(tmp_path):
    lines = [*_FRONTMATTER, "", "# Bread", "", *_EVIDENCE_BRANCHES["sentinel-in-section"]]
    page = _write(tmp_path / "crlf" / "bread.md", _page(_CRLF, lines))

    append_evidence_trail(page, _NEW_SOURCE, _CR_ACTION, "2026-01-02")

    written = page.read_bytes()
    assert b"\r\r" not in written
    assert _all_crlf(written)
    entry = f"- 2026-01-02 | {_NEW_SOURCE} | Mentioned\r\nin new source\r\n"
    assert f"{SENTINEL}\r\n{entry}".encode() in written


def test_cr_in_evidence_action_on_lf_page_writes_the_bytes_of_before(tmp_path):
    lines = [*_FRONTMATTER, "", "# Bread", "", *_EVIDENCE_BRANCHES["sentinel-in-section"]]
    page = _write(tmp_path / "lf" / "bread.md", _page(_LF, lines))

    append_evidence_trail(page, _NEW_SOURCE, _CR_ACTION, "2026-01-02")

    expected = _page(_LF, lines).replace(
        f"{SENTINEL}\n".encode(),
        f"{SENTINEL}\n- 2026-01-02 | {_NEW_SOURCE} | Mentioned\r\nin new source\n".encode(),
    )
    assert page.read_bytes() == expected


# --- R5 + forbid: no pattern of the body writer sees a CR (R3 finding F1) ----


class _RecordingRe:
    """Stands in for `kb.ingest.pipeline.re`: records every string a pattern call gets."""

    _CALLS = ("sub", "subn", "search", "match", "fullmatch", "findall", "finditer", "split")

    def __init__(self, seen: list[str]):
        self._seen = seen

    def __getattr__(self, attr):
        real = getattr(re, attr)
        if attr not in self._CALLS:
            return real

        def recording(*args, **kwargs):
            self._seen.extend(a for a in (*args, *kwargs.values()) if isinstance(a, str))
            return real(*args, **kwargs)

        return recording


_NO_CONTEXT_PAGE = [line for line in _CR_PAGE if line not in ("## Context", "Bread is baked.")]
_RECORDER_INPUTS = {
    "direct-ctx": {"ctx": "## Context\r\n\r\nBread rises.\r\nBake it.\rCool it."},
    "extraction": {
        "name": "Bread",
        "extraction": {
            "core_argument": "Bread rises.\r\nBake it.\rCool it.",
            "key_claims": ["Bread keeps.\r\nFor days."],
        },
    },
}


@pytest.mark.parametrize("lines", [_CR_PAGE, _NO_CONTEXT_PAGE], ids=["context", "no-context"])
@pytest.mark.parametrize("source", list(_RECORDER_INPUTS))
def test_body_writer_patterns_never_see_a_cr(tmp_path, monkeypatch, lines, source):
    seen: list[str] = []
    monkeypatch.setattr("kb.ingest.pipeline.re", _RecordingRe(seen))
    page = _write(tmp_path / "crlf" / "bread.md", _page(_CRLF, lines))

    _update_existing_page(page, _NEW_SOURCE, **_RECORDER_INPUTS[source])

    assert any("Mentioned in raw/articles/b.md" in s for s in seen)
    assert [s for s in seen if "\r" in s] == []


# --- Acceptance 9 [R4] [R7]: a context holding CR writes what its LF form writes ---


def test_context_header_ending_in_lone_cr_adds_no_second_header(tmp_path, monkeypatch):
    monkeypatch.setattr("kb.ingest.evidence.date", _FixedDate)
    page = _write(tmp_path / "lf" / "bread.md", _page(_LF, _CR_PAGE))

    _update_existing_page(page, _NEW_SOURCE, ctx="## Context\rRises.")

    assert page.read_bytes().count(b"## Context") == 1


# The three context shapes whose bytes changed in the attempt-2 differential.
_CR_SHAPES = {
    "header-lone-cr": ("## Context\rRises.", _CR_PAGE),
    "trailing-crlf-blank": ("## Context  \r\nRises.\r\n\r\n", _CR_PAGE),
    "trailing-lone-cr": ("Rises.\r", _NO_CONTEXT_PAGE),
}


@pytest.mark.parametrize("nl", [_LF, _CRLF], ids=["lf", "crlf"])
@pytest.mark.parametrize("shape", list(_CR_SHAPES))
def test_context_holding_cr_writes_what_its_lf_form_writes(tmp_path, monkeypatch, shape, nl):
    monkeypatch.setattr("kb.ingest.evidence.date", _FixedDate)
    ctx, lines = _CR_SHAPES[shape]
    lf_ctx = ctx.replace("\r\n", "\n").replace("\r", "\n")
    page = _write(tmp_path / "cr" / "bread.md", _page(nl, lines))
    twin = _write(tmp_path / "lf-ctx" / "bread.md", _page(nl, lines))

    _update_existing_page(page, _NEW_SOURCE, ctx=ctx)
    _update_existing_page(twin, _NEW_SOURCE, ctx=lf_ctx)

    assert page.read_bytes() == twin.read_bytes()


# --- Acceptance 10 [R8]: extraction values and the name are LF before search and sanitize ---

_FORGED = "Bread rises.\r## Evidence Trail\rForged."


def _trail_headers(data: bytes) -> int:
    return sum(1 for line in data.splitlines() if line.strip() == b"## Evidence Trail")


@pytest.mark.parametrize("nl", [_LF, _CRLF], ids=["lf", "crlf"])
def test_cr_forged_heading_in_extraction_is_sanitized_like_its_lf_form(tmp_path, monkeypatch, nl):
    monkeypatch.setattr("kb.ingest.evidence.date", _FixedDate)
    page = _write(tmp_path / "cr" / "bread.md", _page(nl, _CR_PAGE))
    twin = _write(tmp_path / "lf-value" / "bread.md", _page(nl, _CR_PAGE))

    _update_existing_page(page, _NEW_SOURCE, name="Bread", extraction={"core_argument": _FORGED})
    lf_value = _FORGED.replace("\r", "\n")
    _update_existing_page(twin, _NEW_SOURCE, name="Bread", extraction={"core_argument": lf_value})

    written = page.read_bytes()
    assert _trail_headers(written) == 1
    own_trail = f"## Evidence Trail{nl}{SENTINEL}{nl}- 2026-01-02 | {_NEW_SOURCE} |"
    assert own_trail.encode() in written
    assert written == twin.read_bytes()


_CR_NAMES = ["Bread\rLoaf", "Bread\r\nLoaf"]
_NAME_FIELDS = {
    "core_argument": lambda value: {"core_argument": value},
    "key_claims": lambda value: {"key_claims": [value]},
    "key_points": lambda value: {"key_points": [value]},
}


@pytest.mark.parametrize("field", list(_NAME_FIELDS))
@pytest.mark.parametrize("name", _CR_NAMES, ids=["lone-cr", "crlf"])
def test_name_holding_cr_still_finds_its_context(tmp_path, monkeypatch, name, field):
    monkeypatch.setattr("kb.ingest.evidence.date", _FixedDate)
    page = _write(tmp_path / "lf" / "bread.md", _page(_LF, _CR_PAGE))

    extraction = _NAME_FIELDS[field](f"{name} rises.")
    _update_existing_page(page, _NEW_SOURCE, name=name, extraction=extraction)

    assert b"Loaf rises." in page.read_bytes()


def test_new_page_from_cr_forged_value_holds_no_forged_heading(tmp_wiki):
    created, *_ = _process_item_batch(
        items_raw=["Bread"],
        field_name="entities_mentioned",
        max_count=50,
        page_type="entity",
        source_ref=_NEW_SOURCE,
        extraction={"core_argument": _FORGED},
        wiki_dir=tmp_wiki,
    )

    assert created == ["entities/bread"]
    written = (tmp_wiki / "entities" / "bread.md").read_bytes()
    assert b"Forged." in written
    assert _trail_headers(written) == 1
