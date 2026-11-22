"""T0-KBFIX-STATSDIR (#187): `kb_stats` and `kb stats` use the default wiki directory
when no wiki directory is given.

`kb_stats` passed the result of `_validate_wiki_dir(None)`, which is `None`, to
`kb.graph.cache.get_graph`, whose cache key calls `wiki_dir.resolve()`. Every call
without `wiki_dir` returned `Error computing wiki stats: 'NoneType' object has no
attribute 'resolve'`, and `kb stats` exited 1. The earlier no-argument tests patched
`get_graph` or failed before it, so none reached the real call; these do not patch it.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from kb.cli import cli
from kb.mcp.browse import kb_stats

_PAGE = (
    b"---\n"
    b'title: "Alpha"\n'
    b"source:\n"
    b'  - "raw/articles/a.md"\n'
    b"created: 2026-11-23\n"
    b"updated: 2026-11-23\n"
    b"type: concept\n"
    b"confidence: stated\n"
    b"---\n"
    b"\n"
    b"Alpha body.\n"
)


def _write_one_page(project: Path) -> Path:
    wiki = project / "wiki"
    (wiki / "concepts" / "alpha.md").write_bytes(_PAGE)
    return wiki


def test_kb_stats_without_wiki_dir_reports_the_default_wiki(tmp_kb_env):
    _write_one_page(tmp_kb_env)

    result = kb_stats()

    assert result.startswith("# Wiki Statistics"), result
    assert "**Total pages:** 1" in result
    assert "1 nodes" in result
    assert "Error" not in result


def test_kb_stats_without_wiki_dir_matches_the_explicit_default(tmp_kb_env):
    wiki = _write_one_page(tmp_kb_env)

    assert kb_stats() == kb_stats(wiki_dir=str(wiki))


def test_cli_stats_without_wiki_dir_exits_zero(tmp_kb_env):
    _write_one_page(tmp_kb_env)

    result = CliRunner().invoke(cli, ["stats"])

    assert result.exit_code == 0, result.output
    assert "# Wiki Statistics" in result.output
    assert "**Total pages:** 1" in result.output
