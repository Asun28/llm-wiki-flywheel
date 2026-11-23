---
slug: kb-cite-check
title: "Check the calling model's citations in default kb_query mode (#197)"
spec: specs/kb-cite-check.md
size: T1
status: accepted
created: 2026-11-23T00:25:00Z
---

# Plan: Check the calling model's citations in default kb_query mode (#197) (from specs/kb-cite-check.md)

## 1. Goal and boundaries
Give default-mode `kb_query` callers a way to check their citations against the pages they were given: a new MCP tool `kb_check_citations` and a `context_pages` line in the `kb_query` response. Cut: CLI command, server-side token, answer rewriting. Success: spec acceptance 1-8 on the final integrated SHA.

## 2. Minimal acceptable loop
Card 1 adds the tool and freezes its input format. Card 2 makes `kb_query` emit that format and proves the round trip (response line passed back unchanged gives `Accepted`). Each card: RED test, change, GREEN, R3, merge. Then VERIFY-ARC.

## 3. Tech stack
none this version

## 4. Directory structure
none this version (new test files only)

## 4.5 Module design
- `kb.mcp.core.kb_check_citations` (CHECK): parse ids, `extract_citations`, `partition_citations`, format text.
- `kb.mcp.app._TOOL_GROUPS` (CHECK): Query group lists the new tool.
- `kb.mcp.core.kb_query` default branch (ECHO): `context_pages:` line and instruction before the fence.

## 5. Data model and state machine
none this version

## 6. Contracts and core interfaces
`kb_check_citations(answer: str, context_pages: str = "") -> str` with the R2 input format (frozen at CHECK merge). Default `kb_query` response: two added lines outside the fence. `extract_citations` / `partition_citations` unchanged.

## Files that change
- src/kb/mcp/core.py
- src/kb/mcp/app.py
- tests/test_kbcite_check_citations.py (new)
- tests/test_kbcite_query_echo.py (new)
- README.md
- README.zh-CN.md
- docs/reference/mcp-servers.md
- CHANGELOG.md
- CHANGELOG-history.md
- CLAUDE.md

## Order of work
1. T1-KBCITE-CHECK (freeze): RED tests for acceptance 1-5, then the tool, the instruction listing, tool-count docs.
2. T1-KBCITE-ECHO (after CHECK merges): RED tests for acceptance 6-7, then the `kb_query` echo.
3. VERIFY-ARC on the final SHA: full suite, ruff, `scripts/verify_docs.py`, round trip through the MCP surface.

## 7. Task split (dependencies and parallel windows)

| Card | Priority | Output | depends_on | Parallel window | Freeze point |
|---|---|---|---|---|---|
| T1-KBCITE-CHECK | MUST | `kb_check_citations` MCP tool, listed and documented | - | - | yes |
| T1-KBCITE-ECHO | MUST | default `kb_query` emits `context_pages:` line and check instruction | T1-KBCITE-CHECK | - | - |

Both cards edit `src/kb/mcp/core.py` and the CHANGELOG files, so they run one at a time.

## Risks
- Existing default-mode `kb_query` tests that compare whole responses would break on the added lines; ECHO's sweep lists them before the change, and no existing test may be edited (if one pins the exact text, STOP for an owner ruling).
- `core.py` imports `WIKI_DIR` / `RAW_DIR` as module bindings; the tool must read them through `kb.config` at call time or the sandbox fixture can point it at the real wiki.
- The tool-registration and instruction tests (`tests/test_mcp_core.py:1830`, `:1910`) require the instruction listing and the registered set to stay equal.

## Proof
- Acceptance 1-5: `tests/test_kbcite_check_citations.py`.
- Acceptance 6-7: `tests/test_kbcite_query_echo.py`.
- Acceptance 8: `python scripts/verify_docs.py`, grep of the three docs.
- Integrated: full `python -m pytest` and `ruff check src/ tests/` on the final SHA.

## 10. After merge
none this version (development-only target)
