---
id: T1-KBCITE-CHECK
title: "`kb_check_citations` MCP tool checks a caller's citations against the given page ids (#197)"
status: todo
branch: T1-KBCITE-CHECK
worktree: D:\wt\llm-wiki-flywheel\T1-KBCITE-CHECK
allow_paths:
  - src/kb/mcp/core.py
  - src/kb/mcp/app.py
  - tests/test_kbcite_check_citations.py
  - README.md
  - README.zh-CN.md
  - docs/reference/mcp-servers.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T1-KBCITE-CHECK.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbcite_check_citations.py tests/test_mcp_core.py tests/test_cycle95_mcp_async_offload.py tests/test_kbfix_query_citation_context.py tests/test_cycle34_release_hygiene.py -q
dod_exit: 0
requirements:
  - R1. The MCP server shall register a tool `kb_check_citations(answer: str, context_pages: str = "") -> str` that reads no page content and writes nothing.
  - R2. The tool shall parse `context_pages` by dropping one leading `context_pages:` label (case-insensitive) if present, splitting the rest on commas and whitespace, and dropping empty items.
  - R3. The tool shall extract citations from `answer` with `kb.query.citations.extract_citations` and split them with `partition_citations(citations, wiki_ids=<parsed ids>, raw_ids=[], wiki_dir=..., raw_dir=...)`, the two directories read from `kb.config` at call time (attribute lookup, not the `core.py` import-time bindings).
  - R4. The tool shall return a line `Accepted (<n>): ` followed by the accepted citations comma-separated, then a line `Rejected (<m>):` followed by one line per rejected citation `  - <path> (<type>): <reason>`; `n` and `m` are always shown, `0` included.
  - R5. WHEN `answer` holds no citation, the tool shall return `No citations found in answer.`
  - R6. IF `answer` is empty or whitespace, or longer than `MAX_CITATION_CHECK_ANSWER_CHARS` (200_000, a `core.py` module constant), or the parsed ids number more than `kb.config.MAX_SEARCH_RESULTS`, THEN the tool shall return a string starting `Error: ` naming the limit, without calling `extract_citations`.
  - R7. The tool shall be listed in the `Query` group of `kb.mcp.app._TOOL_GROUPS` and shall not be registered through `register_long_tool`.
acceptance:
  - 1. `test_kbcite_check_citations.py`: in the `tmp_kb_env` sandbox with three concept pages written as bytes, an answer citing `[[concepts/a]]` (in `context_pages`), `[[concepts/b]]` (exists, not in it) and `[[concepts/missing]]` returns `Accepted (1)` naming `concepts/a`, and `Rejected (2)` with `concepts/b (wiki): out_of_context` and `concepts/missing (wiki): nonexistent`. [R1] [R3] [R4] [dod arm 2]
  - 2. Same file: `context_pages` given as `"context_pages: concepts/a, concepts/c"`, `"concepts/a,concepts/c"` and `"concepts/a concepts/c"` give the same result; `[[CONCEPTS/A]]` is accepted. [R2] [R3] [dod arm 2]
  - 3. Same file: `[ref: raw/articles/x.md]` with that raw file present in the sandbox is rejected `out_of_context`. [R3] [dod arm 2]
  - 4. Same file: an answer with no citation returns `No citations found in answer.`; empty answer, a 200_001-char answer and 101 ids each return a string starting `Error: `, with `kb.query.citations.extract_citations` spied and not called. [R5] [R6] [dod arm 2]
  - 5. Same file: `kb_check_citations` is in `mcp.list_tools()`, under `### Query` in `mcp.instructions`, and not in `kb.mcp._offload.LONG_TOOL_NAMES`; `test_mcp_core.py` and `test_cycle95_mcp_async_offload.py` pass unchanged. [R7] [dod arms 2-6]
  - 6. `README.md`, `README.zh-CN.md` and `docs/reference/mcp-servers.md` read 29 tools and list `kb_check_citations`; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the `State` line of `CLAUDE.md` equals `python scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 120
plan_ref: plans/kb-cite-check.md#7
freeze: true
sweep: "Tool listings: `src/kb/mcp/app.py:_TOOL_GROUPS` (Query group), `tests/test_mcp_core.py:1830` (subset check, unchanged) and `:1910` (instruction list == registered set). Tool counts '28' in `README.md` (lines 13, 22, 63, 273, 298, 421), `README.zh-CN.md`, `docs/reference/mcp-servers.md:15`. Long-tool set pinned in `tests/test_cycle95_mcp_async_offload.py:43` (the new tool must stay out of it). Reused helpers: `kb.query.citations.extract_citations`, `partition_citations` (unchanged)."
forbid:
  - "a change to `extract_citations` or `partition_citations`"
  - "any edit to an existing test"
  - "a model call or network request in the tool or its tests"
  - "reading page content or writing any file from the tool"
non_goals:
  - "the `context_pages:` line in `kb_query` output (card T1-KBCITE-ECHO)"
  - "a CLI command"
  - "a server-side token for the ids"
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixtures as bytes. Every call runs inside `tmp_kb_env`. Call the sync module attribute `kb.mcp.core.kb_check_citations` directly. RED: acceptance 1-5 fail on main (no such tool)."
---

# T1-KBCITE-CHECK

## Deliverable
New MCP tool `kb_check_citations(answer, context_pages)`: the calling model passes the answer it wrote from default-mode `kb_query` context and the page ids it was given; the tool returns the accepted citations and the rejected ones with reason `out_of_context` or `nonexistent`, using `partition_citations` unchanged.

## Why
Issue #197. In default MCP mode no answer reaches `query_wiki`, so the #189 citation check never runs.

## Owner decisions (2026-11-23)
1. New MCP tool, not a `kb_query` parameter.
2. Ids are echoed by `kb_query` and passed back by the caller; no server-side token.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbcite_check_citations.py tests/test_mcp_core.py tests/test_cycle95_mcp_async_offload.py tests/test_kbfix_query_citation_context.py tests/test_cycle34_release_hygiene.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED on main 82fee07 with the new test file: 15 failed (`ImportError: cannot import name 'kb_check_citations'`; tool not in `mcp.list_tools()`).

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. in-context accepted, out-of-context and nonexistent rejected | `test_in_context_accepted_others_rejected_with_reasons` | pass |
| 2. `context_pages` forms, upper-case citation | `test_context_pages_forms_parse_the_same` (5 forms), `test_upper_case_citation_of_an_in_context_id_is_accepted` | pass |
| 3. raw citation rejected `out_of_context` | `test_raw_citation_is_never_in_default_context` | pass |
| 4. no citation; limits without extraction | `test_no_citation`, `test_limits_return_error_without_extracting` (4 cases), `test_limits_are_at_the_boundary` | pass |
| 5. registered, Query group, not long; existing registry tests unchanged | `test_tool_registered_in_query_group_and_short`, `tests/test_mcp_core.py`, `tests/test_cycle95_mcp_async_offload.py` | pass |
| 6. docs 29 tools, CHANGELOG entries, CLAUDE.md counts | `python scripts/verify_docs.py`: docs in sync (4020 tests, 231 files) | pass (reviewer-verified) |

DoD: `ruff check src/ tests/` all checks passed; pytest 294 passed, 2 skipped; exit 0.