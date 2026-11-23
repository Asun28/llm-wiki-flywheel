"""T1-KBCITE-CHECK (#197): `kb_check_citations` checks a caller's citations.

In default MCP mode `kb_query` returns wiki context and the calling model writes the
answer, so the #189 check in `query_wiki` never sees it. `kb_check_citations` takes that
answer and the page ids the caller was given and reports which citations were in that
context, using `kb.query.citations.partition_citations` unchanged.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


def _page(title: str) -> bytes:
    return (
        "---\n"
        f'title: "{title}"\n'
        "source:\n"
        '  - "raw/articles/x.md"\n'
        "created: 2026-11-23\n"
        "updated: 2026-11-23\n"
        "type: concept\n"
        "confidence: stated\n"
        "---\n"
        "\n"
        f"{title} body.\n"
    ).encode()


@pytest.fixture
def wiki(tmp_kb_env: Path) -> Path:
    wiki_dir = tmp_kb_env / "wiki"
    (wiki_dir / "concepts").mkdir(parents=True, exist_ok=True)
    for name in ("a", "b", "c"):
        (wiki_dir / "concepts" / f"{name}.md").write_bytes(_page(name.upper()))
    raw_dir = tmp_kb_env / "raw" / "articles"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "x.md").write_bytes(b"raw source\n")
    return wiki_dir


def _check(answer: str, context_pages: str = "") -> str:
    from kb.mcp.core import kb_check_citations

    return kb_check_citations(answer, context_pages)


def test_in_context_accepted_others_rejected_with_reasons(wiki):
    out = _check(
        "A [[concepts/a]]. B [[concepts/b]]. Gone [[concepts/missing]].",
        "concepts/a",
    )
    lines = out.splitlines()
    assert lines[0] == "Accepted (1): concepts/a"
    assert lines[1] == "Rejected (2):"
    assert "  - concepts/b (wiki): out_of_context" in lines
    assert "  - concepts/missing (wiki): nonexistent" in lines


@pytest.mark.parametrize(
    "context_pages",
    [
        "context_pages: concepts/a, concepts/c",
        "CONTEXT_PAGES: concepts/a, concepts/c",
        "concepts/a,concepts/c",
        "concepts/a concepts/c",
        "  concepts/a ,\n concepts/c ,, ",
    ],
)
def test_context_pages_forms_parse_the_same(wiki, context_pages):
    out = _check("[[concepts/a]] [[concepts/c]] [[concepts/b]]", context_pages)
    lines = out.splitlines()
    assert lines[0] == "Accepted (2): concepts/a, concepts/c"
    assert lines[1:] == ["Rejected (1):", "  - concepts/b (wiki): out_of_context"]


def test_upper_case_citation_of_an_in_context_id_is_accepted(wiki):
    out = _check("See [[CONCEPTS/A]].", "concepts/a")
    assert out.splitlines() == ["Accepted (1): CONCEPTS/A", "Rejected (0):"]


def test_raw_citation_is_never_in_default_context(wiki):
    out = _check("Per [ref: raw/articles/x.md].", "concepts/a")
    assert out.splitlines() == [
        "Accepted (0): ",
        "Rejected (1):",
        "  - raw/articles/x.md (raw): out_of_context",
    ]


def test_no_citation(wiki):
    assert _check("No citations here.", "concepts/a") == "No citations found in answer."


@pytest.mark.parametrize(
    ("answer", "context_pages"),
    [
        ("", "concepts/a"),
        ("   \n\t", "concepts/a"),
        ("x" * 200_001, "concepts/a"),
        ("[[concepts/a]]", ", ".join(f"concepts/p{i}" for i in range(101))),
    ],
    ids=["empty", "whitespace", "too-long", "too-many-ids"],
)
def test_limits_return_error_without_extracting(wiki, monkeypatch, answer, context_pages):
    calls: list[str] = []

    def spy(text):
        calls.append(text)
        return []

    monkeypatch.setattr("kb.query.citations.extract_citations", spy)
    out = _check(answer, context_pages)
    assert out.startswith("Error: ")
    assert calls == []


def test_limits_are_at_the_boundary(wiki):
    from kb.config import MAX_SEARCH_RESULTS
    from kb.mcp.core import MAX_CITATION_CHECK_ANSWER_CHARS

    assert MAX_CITATION_CHECK_ANSWER_CHARS == 200_000
    answer = "[[concepts/a]]".ljust(MAX_CITATION_CHECK_ANSWER_CHARS, " ")
    ids = ", ".join(["concepts/a"] + [f"concepts/p{i}" for i in range(MAX_SEARCH_RESULTS - 1)])
    assert _check(answer, ids).splitlines()[0] == "Accepted (1): concepts/a"


def test_tool_registered_in_query_group_and_short():
    from kb.mcp import mcp
    from kb.mcp._offload import LONG_TOOL_NAMES

    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert "kb_check_citations" in names
    assert "kb_check_citations" not in LONG_TOOL_NAMES

    instructions = mcp.instructions or ""
    query_section = instructions.split("### Query", 1)[1].split("###", 1)[0]
    assert "`kb_check_citations`" in query_section
