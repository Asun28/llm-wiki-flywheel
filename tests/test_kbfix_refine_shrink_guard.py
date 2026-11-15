"""T1-KBFIX-SHRINK (#162): `refine_page` refuses a body under half the current one.

`refine_page` used to accept any non-empty body, so one call could replace a
page with 1% of it. It now refuses a new body shorter than
`REFINE_MIN_BODY_RATIO` (0.5) times the current body, both counted after CRLF
to LF and `strip()`, unless the caller passes `allow_shrink=True`; an override
that crosses the floor is recorded in the review-history row.

Fixtures are written as BYTES so the CRLF tests control the exact line breaks
on Windows (`write_text` would translate `\\n`).
"""

import asyncio
import inspect
import json
from pathlib import Path

import pytest

from kb.review.refiner import load_review_history, refine_page

FRONTMATTER = (
    '---\ntitle: "Shrink Guard"\nsource:\n  - "raw/articles/a.md"\n'
    "created: 2026-01-01\nupdated: 2026-01-01\ntype: concept\nconfidence: stated\n---\n\n"
)
BODY_200 = "x" * 200
OVERRIDE_KEYS = ("allow_shrink", "previous_body_length", "new_body_length")


def _write_page(wiki: Path, body: str, *, frontmatter: str = FRONTMATTER, crlf=False) -> Path:
    text = frontmatter + body + "\n"
    if crlf:
        text = text.replace("\n", "\r\n")
    path = wiki / "concepts" / "shrink.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


@pytest.fixture
def env(tmp_path: Path):
    wiki = tmp_path / "wiki"
    history = tmp_path / ".data" / "review_history.json"
    history.parent.mkdir(parents=True, exist_ok=True)
    return wiki, history


def _refine(wiki: Path, history: Path, body: str, **kw) -> dict:
    return refine_page("concepts/shrink", body, "notes", wiki_dir=wiki, history_path=history, **kw)


def _only_row(history: Path) -> dict:
    rows = load_review_history(history)
    assert len(rows) == 1
    return rows[0]


# ── Acceptance 1: the 50% floor ─────────────────────────────────────────────


def test_a_body_just_under_half_is_refused_with_both_lengths_and_the_ratio(env):
    wiki, history = env
    page = _write_page(wiki, BODY_200)
    history.write_bytes(b'[{"page_id": "older", "status": "applied"}]')
    page_before = page.read_bytes()
    history_before = history.read_bytes()

    result = _refine(wiki, history, "y" * 99)

    assert result == {
        "error": (
            "New body has 99 characters, under 0.5 of the current body's 200 "
            "(ratio 0.495 < 0.5); pass allow_shrink=True to replace it anyway."
        )
    }
    assert page.read_bytes() == page_before
    assert history.read_bytes() == history_before


def test_a_body_of_exactly_half_is_accepted(env):
    wiki, history = env
    page = _write_page(wiki, BODY_200)

    result = _refine(wiki, history, "y" * 100)

    assert result.get("updated") is True
    assert "y" * 100 in page.read_text(encoding="utf-8")
    assert "x" * 200 not in page.read_text(encoding="utf-8")


# ── Acceptance 2: the recorded override ─────────────────────────────────────


def test_a_one_percent_body_is_refused_without_the_override(env):
    wiki, history = env
    page = _write_page(wiki, BODY_200)
    page_before = page.read_bytes()

    result = _refine(wiki, history, "ok")

    assert "error" in result
    assert "New body has 2 characters" in result["error"]
    assert page.read_bytes() == page_before
    assert not history.exists()


def test_the_override_writes_the_body_and_records_it_in_history(env):
    wiki, history = env
    page = _write_page(wiki, BODY_200)

    result = _refine(wiki, history, "ok", allow_shrink=True)

    assert result.get("updated") is True
    assert page.read_text(encoding="utf-8").endswith("\n\nok\n")
    row = _only_row(history)
    assert row["status"] == "applied"
    assert {k: row.get(k) for k in OVERRIDE_KEYS} == {
        "allow_shrink": True,
        "previous_body_length": 200,
        "new_body_length": 2,
    }


def test_a_write_above_the_floor_records_no_override_keys(env):
    wiki, history = env
    _write_page(wiki, BODY_200)

    _refine(wiki, history, "y" * 100)

    row = _only_row(history)
    assert row["status"] == "applied"
    assert [k for k in OVERRIDE_KEYS if k in row] == []


def test_allow_shrink_on_a_write_above_the_floor_records_no_override_keys(env):
    wiki, history = env
    _write_page(wiki, BODY_200)

    _refine(wiki, history, "y" * 100, allow_shrink=True)

    row = _only_row(history)
    assert row["status"] == "applied"
    assert [k for k in OVERRIDE_KEYS if k in row] == []


# ── Acceptance 3: placement after the existing gates ───────────────────────


def test_malformed_frontmatter_is_reported_before_the_shrink_floor(env):
    wiki, history = env
    bad_fm = '---\ntitle: "Bad"\n\tsource: tab-indented\n---\n\n'
    page = _write_page(wiki, BODY_200, frontmatter=bad_fm)
    page_before = page.read_bytes()

    result = _refine(wiki, history, "ok")

    assert result["error"].startswith("Malformed frontmatter YAML in concepts/shrink")
    assert page.read_bytes() == page_before


def test_a_whitespace_only_body_gets_the_empty_body_error(env):
    wiki, history = env
    _write_page(wiki, BODY_200)

    result = _refine(wiki, history, "  \r\n\t ")

    assert result == {"error": "updated_content cannot be empty."}


def test_a_page_with_an_empty_body_accepts_any_non_empty_body(env):
    wiki, history = env
    page = _write_page(wiki, "")

    result = _refine(wiki, history, "z")

    assert result.get("updated") is True
    assert page.read_text(encoding="utf-8").endswith("\n\nz\n")
    assert [k for k in OVERRIDE_KEYS if k in _only_row(history)] == []


def test_crlf_in_the_new_body_is_counted_as_one_character(env):
    # 50 + LF + 48 = 99 after normalisation (refused); 100 if CRLF counted.
    wiki, history = env
    _write_page(wiki, BODY_200)

    result = _refine(wiki, history, "a" * 50 + "\r\n" + "b" * 48)

    assert result.get("error", "").startswith("New body has 99 characters")


def test_crlf_in_the_current_body_is_counted_as_one_character(env):
    # 100 + LF + 99 = 200 after normalisation, so 100 is exactly half (accepted);
    # counting CRLF would make it 201 and refuse the 100-character body.
    wiki, history = env
    _write_page(wiki, "x" * 100 + "\n" + "w" * 99, crlf=True)

    result = _refine(wiki, history, "y" * 100)

    assert result.get("updated") is True


# ── Acceptance 4: call-time ratio ──────────────────────────────────────────


def test_the_ratio_is_read_at_call_time(env, monkeypatch):
    import kb.config

    wiki, history = env
    page = _write_page(wiki, BODY_200)
    page_before = page.read_bytes()
    monkeypatch.setattr(kb.config, "REFINE_MIN_BODY_RATIO", 0.9, raising=False)

    result = _refine(wiki, history, "y" * 150)

    assert result == {
        "error": (
            "New body has 150 characters, under 0.9 of the current body's 200 "
            "(ratio 0.750 < 0.9); pass allow_shrink=True to replace it anyway."
        )
    }
    assert page.read_bytes() == page_before


# ── Acceptance 5: MCP pass-through and signature ───────────────────────────


def test_the_mcp_tool_refuses_a_one_percent_body_and_writes_it_with_the_override(tmp_kb_env):
    from kb.mcp import quality

    page = _write_page(tmp_kb_env / "wiki", BODY_200)
    page_before = page.read_bytes()

    refused = quality.kb_refine_page("concepts/shrink", "ok", "trim")
    assert refused.startswith("Error: New body has 2 characters")
    assert page.read_bytes() == page_before

    written = quality.kb_refine_page("concepts/shrink", "ok", "trim", allow_shrink=True)
    assert written.startswith("Refined: concepts/shrink")
    assert page.read_text(encoding="utf-8").endswith("\n\nok\n")
    history = tmp_kb_env / ".data" / "review_history.json"
    row = json.loads(history.read_text(encoding="utf-8"))[-1]
    assert row["allow_shrink"] is True


def test_refine_page_takes_allow_shrink_as_keyword_only_defaulting_to_false():
    param = inspect.signature(refine_page).parameters["allow_shrink"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY
    assert param.default is False


def test_the_registered_mcp_tool_schema_lists_allow_shrink():
    from kb.mcp import mcp

    tool = asyncio.run(mcp.get_tool("kb_refine_page"))
    prop = tool.parameters["properties"]["allow_shrink"]
    assert prop["type"] == "boolean"
    assert prop["default"] is False
    assert "allow_shrink" not in tool.parameters.get("required", [])
