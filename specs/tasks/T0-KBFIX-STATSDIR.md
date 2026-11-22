---
id: T0-KBFIX-STATSDIR
title: "kb_stats and kb stats use the default wiki directory when wiki_dir is omitted (#187)"
status: todo
branch: T0-KBFIX-STATSDIR
worktree: D:\wt\llm-wiki-flywheel\T0-KBFIX-STATSDIR
allow_paths:
  - src/kb/mcp/browse.py
  - tests/test_kbfix_stats_default_wiki_dir.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T0-KBFIX-STATSDIR.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_stats_default_wiki_dir.py tests/test_mcp_browse_health.py tests/test_cycle27_cli_parity.py tests/test_cycle31_cli_parity.py tests/test_cycle95_mcp_async_offload.py tests/test_mcp_core.py tests/test_tier1_audit_v095.py -q
dod_exit: 0
requirements:
  - R1. WHEN `kb_stats` is called without `wiki_dir`, it shall compute coverage and graph statistics for the default wiki directory (`kb.mcp.browse.WIKI_DIR`, read at call time) and return the statistics text, not an error string.
  - R2. WHEN `kb stats` is run without `--wiki-dir`, it shall print the statistics and exit 0.
acceptance:
  - 1. `test_kbfix_stats_default_wiki_dir.py`: in the `tmp_kb_env` sandbox with one concept page written as bytes, `kb_stats()` with no argument and no patch on `kb.graph.cache.get_graph` returns text that starts with `# Wiki Statistics`, contains `**Total pages:** 1` and `1 nodes`, and does not contain `Error`. [R1] [dod arm 2]
  - 2. Same file: in the same sandbox, `kb_stats()` returns the same text as `kb_stats(wiki_dir=str(<sandbox wiki dir>))`, so coverage and graph come from the one default directory. [R1] [dod arm 2]
  - 3. Same file: in the same sandbox, `CliRunner().invoke(cli, ["stats"])` exits 0 and its output contains `# Wiki Statistics` and `**Total pages:** 1`. [R2] [dod arm 2]
  - 4. Every DoD test file passes and no existing test is edited; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 80
sweep: "Callers of `kb.graph.cache.get_graph`: `evolve/analyzer.py:129`, `graph/export.py:85`, `lint/augment/collector.py:49`, `lint/checks/cycles.py:22`, `lint/checks/orphan.py:29` and `lint/runner.py:62,103` each run `wiki_dir = wiki_dir or <WIKI_DIR>` first; `lint/semantic.py:231` passes `pages=`, which bypasses the cache key. `mcp/browse.py:373` is the only caller that can pass `None`. Tests that call `kb_stats` or the `stats` command: `test_mcp_browse_health.py`, `test_cycle27_cli_parity.py`, `test_cycle31_cli_parity.py`, `test_cycle95_mcp_async_offload.py`, `test_mcp_core.py`, `test_tier1_audit_v095.py`, all in the DoD."
forbid:
  - "a change to `kb.graph.cache.get_graph`, `_validate_wiki_dir` or `analyze_coverage`"
  - "any edit to an existing test"
  - "a model call or network request in tests"
non_goals:
  - "#188 (`query_wiki` passes `None` to `load_purpose`): same class, separate issue and card"
  - "making `get_graph` accept `None`: every other caller already resolves the default, and the cache key must name a real directory"
diagnosis:
  root_cause: "`kb_stats` (`src/kb/mcp/browse.py:361`) passes the result of `_validate_wiki_dir(wiki_dir)` to `analyze_coverage` and to `kb.graph.cache.get_graph`. For `wiki_dir=None` that result is `None`. `analyze_coverage` falls back to its own `WIKI_DIR`, but `get_graph` builds its cache key with `wiki_dir.resolve()` (`src/kb/graph/cache.py:129`) and raises `AttributeError`. The `kb stats` CLI calls `kb_stats(wiki_dir=None)` and exits 1. Reproduced on main 5906574 with a one-page temp wiki: `kb_stats()` returns `Error computing wiki stats: 'NoneType' object has no attribute 'resolve'`; `kb_stats(wiki_dir=<same dir>)` returns the statistics. Introduced by ad17c03 (cycle 68), which routed the call through the cache. The existing no-argument tests patch `kb.graph.cache.get_graph` or make `analyze_coverage` raise first, so none reached the real call. Fix: in `kb_stats`, after validation, set `wiki_path = WIKI_DIR` when it is `None` (the module-level name `kb_read_page` and `kb_list_pages` already use, rebound by the test sandbox), and pass that one path to both `analyze_coverage` and `get_graph`."
  same_class: "#188 (`query_wiki` -> `load_purpose(None)`), filed separately. No other `get_graph` caller can receive `None` (see sweep)."
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixtures as bytes. Every call runs inside `tmp_kb_env`. RED: acceptance 1, 2 and 3 fail on the unfixed code (error string, CLI exit 1)."
---

# T0-KBFIX-STATSDIR

## Deliverable
`kb_stats()` and `kb stats` with no wiki directory argument report statistics for the default wiki directory instead of `Error computing wiki stats: 'NoneType' object has no attribute 'resolve'`.

## Why
Issue #187. The default invocation of a read-only health command fails for every user since cycle 68.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_stats_default_wiki_dir.py tests/test_mcp_browse_health.py tests/test_cycle27_cli_parity.py tests/test_cycle31_cli_parity.py tests/test_cycle95_mcp_async_offload.py tests/test_mcp_core.py tests/test_tier1_audit_v095.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED at ef1ef30: `test_kb_stats_without_wiki_dir_reports_the_default_wiki`, `test_kb_stats_without_wiki_dir_matches_the_explicit_default` and `test_cli_stats_without_wiki_dir_exits_zero` 3 failed (`AttributeError: 'NoneType' object has no attribute 'resolve'` from `kb/graph/cache.py:129`).

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. `kb_stats()` with no argument, no patch on `get_graph`: statistics for the one-page sandbox wiki | `test_kb_stats_without_wiki_dir_reports_the_default_wiki` | pass |
| 2. `kb_stats()` equals `kb_stats(wiki_dir=<sandbox wiki>)` | `test_kb_stats_without_wiki_dir_matches_the_explicit_default` | pass |
| 3. `kb stats` exits 0 with the statistics | `test_cli_stats_without_wiki_dir_exits_zero` | pass |
| 4. DoD green, no existing test edited, CHANGELOG / CHANGELOG-history entries, CLAUDE.md counts | DoD below; `git diff main --stat -- tests/` lists only the new file; `python scripts/verify_docs.py`: 3988 tests, 228 files, docs in sync | pass (reviewer-verified) |
