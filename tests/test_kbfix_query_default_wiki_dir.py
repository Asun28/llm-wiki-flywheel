"""T0-KBFIX-QUERYDIR (#188): `query_wiki`, `kb query` and `kb_query(use_api=True)` use
the default wiki directory when no wiki directory is given.

`query_wiki` passed its `wiki_dir` argument, `None` by default, to `load_purpose`, which
evaluates `wiki_dir / "purpose.md"`. Whenever a page matched the question, every call
without `wiki_dir` raised `QueryError: unsupported operand type(s) for /: 'NoneType' and
'str'` before the model call, and `kb query` exited 1. These tests stub only the model
call (`kb.query.engine.call_llm`); `load_purpose` and the search run for real.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from kb.cli import cli
from kb.mcp.core import kb_query

_QUESTION = "What is hydration?"
_ANSWER = "Hydration attaches state to server-rendered HTML [[concepts/hydration]]."
_PURPOSE = "Focus on frontend rendering performance (purpose marker 7f3a)."

_PAGE = (
    b"---\n"
    b'title: "Hydration"\n'
    b"source:\n"
    b'  - "raw/articles/hydration.md"\n'
    b"created: 2026-11-23\n"
    b"updated: 2026-11-23\n"
    b"type: concept\n"
    b"confidence: stated\n"
    b"---\n"
    b"\n"
    b"Hydration is the process of attaching state and event handlers to "
    b"server-rendered HTML.\n"
)


@pytest.fixture
def query_sandbox(tmp_kb_env: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """One matching page and a purpose.md in the sandbox wiki; the model call recorded."""
    monkeypatch.setenv("KB_DISABLE_VECTORS", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    wiki = tmp_kb_env / "wiki"
    (wiki / "concepts" / "hydration.md").write_bytes(_PAGE)
    (wiki / "purpose.md").write_bytes(_PURPOSE.encode("utf-8") + b"\n")

    prompts: list[str] = []

    def _record(prompt, *args, **kwargs):
        prompts.append(prompt)
        return _ANSWER

    monkeypatch.setattr("kb.query.engine.call_llm", _record)
    return prompts


def test_query_wiki_without_wiki_dir_reads_the_default_purpose(query_sandbox):
    from kb.query.engine import query_wiki

    result = query_wiki(_QUESTION)

    assert result["answer"] == _ANSWER
    assert len(query_sandbox) == 1
    assert _PURPOSE in query_sandbox[0]


def test_cli_query_without_wiki_dir_exits_zero(query_sandbox):
    result = CliRunner().invoke(cli, ["query", _QUESTION])

    assert result.exit_code == 0, result.output
    assert _ANSWER in result.output


def test_kb_query_use_api_without_wiki_dir_returns_the_answer(query_sandbox):
    result = kb_query(_QUESTION, use_api=True)

    assert not result.startswith("Error"), result
    assert _ANSWER in result
