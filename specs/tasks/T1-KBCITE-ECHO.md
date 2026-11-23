---
id: T1-KBCITE-ECHO
title: "Default `kb_query` response states its context page ids and points to `kb_check_citations` (#197)"
status: todo
branch: T1-KBCITE-ECHO
worktree: D:\wt\llm-wiki-flywheel\T1-KBCITE-ECHO
allow_paths:
  - src/kb/mcp/core.py
  - tests/test_kbcite_query_echo.py
  - docs/reference/mcp-servers.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T1-KBCITE-ECHO.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbcite_query_echo.py tests/test_kbcite_check_citations.py tests/test_mcp_core.py tests/test_cycle70_prompt_safety.py tests/test_cycle19_mcp_monkeypatch_migration.py tests/test_phase45_theme4_error_handling.py tests/test_compiler_mcp_v093.py tests/test_kbfix_query_default_wiki_dir.py tests/test_cycle16_kb_query_save_as.py -q
dod_exit: 0
requirements:
  - R8. WHEN default-mode `kb_query` (no `use_api`) returns pages, its response shall contain a line `context_pages: <id>, <id>, ...` listing the ids of the returned pages in the order of their `--- Page: <id>` sections, placed before the `wrap_wiki_context` fence.
  - R9. WHEN default-mode `kb_query` returns pages, its response shall contain, before the fence, an instruction to call `kb_check_citations` with the answer and the `context_pages` line.
  - R10. Default-mode `kb_query` paths that return no pages (empty question, no results, search error) shall return the same text as before this change.
acceptance:
  - 1. `test_kbcite_query_echo.py`: with `kb.query.engine.search_pages` stubbed to return two pages (`concepts/a`, `concepts/b`, in that order) and trust scores stubbed, the default `kb_query` response has exactly one line `context_pages: concepts/a, concepts/b` and a line naming `kb_check_citations`, both at offsets before `<wiki_context>`. [R8] [R9] [dod arm 2]
  - 2. Same file: in the `tmp_kb_env` sandbox with both pages written as bytes, passing that `context_pages:` line unchanged to `kb_check_citations` with an answer citing `[[concepts/a]]` and `[[concepts/b]]` returns `Accepted (2)` and `Rejected (0)`. [R8] [dod arm 2]
  - 3. Same file: with `search_pages` stubbed to return `[]`, the response equals the no-results text on main. [R10] [dod arm 2]
  - 4. Every DoD test file passes and no existing test is edited; `docs/reference/mcp-servers.md` describes the `context_pages:` line; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the `State` line of `CLAUDE.md` equals `python scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on:
  - T1-KBCITE-CHECK
budget: 90
plan_ref: plans/kb-cite-check.md#7
sweep: "Default-branch builder: `src/kb/mcp/core.py:419-444` (header lines, then `wrap_wiki_context`). Tests calling `kb_query` default mode: `test_mcp_core.py` (21 calls), `test_cycle70_prompt_safety.py:206` (wrap spy), `test_cycle19_mcp_monkeypatch_migration.py`, `test_phase45_theme4_error_handling.py`, `test_compiler_mcp_v093.py`, `test_kbfix_query_default_wiki_dir.py`, `test_cycle16_kb_query_save_as.py`; none matches the header text verbatim (grep of `Query Context for` / `Cite sources with` in tests: no hits)."
forbid:
  - "a change inside the `wrap_wiki_context` fenced block"
  - "any edit to an existing test"
  - "a model call or network request in tests"
non_goals:
  - "the `use_api=True` branch (already checked by `query_wiki`)"
  - "raw-source fallback in default mode"
hygiene: "Run the DoD with the main checkout's `.venv` active. Stub `kb.query.engine.search_pages` and `kb.feedback.reliability.compute_trust_scores` (owner modules). Write fixtures as bytes inside `tmp_kb_env`. RED: acceptance 1-2 fail on main (no `context_pages:` line)."
---

# T1-KBCITE-ECHO

## Deliverable
Default-mode `kb_query` adds, before the fenced wiki context, a `context_pages: <ids>` line and an instruction to check the answer with `kb_check_citations`. Passing the line back unchanged gives the tool the ids that were in the context.

## Why
Issue #197, owner decision 2: the caller echoes the ids; no server state.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbcite_query_echo.py tests/test_kbcite_check_citations.py tests/test_mcp_core.py tests/test_cycle70_prompt_safety.py tests/test_cycle19_mcp_monkeypatch_migration.py tests/test_phase45_theme4_error_handling.py tests/test_compiler_mcp_v093.py tests/test_kbfix_query_default_wiki_dir.py tests/test_cycle16_kb_query_save_as.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
