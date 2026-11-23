---
slug: kb-cite-check
title: "Check the calling model's citations in default kb_query mode (#197)"
intent: intent/kb-cite-check.md
status: accepted
created: 2026-11-23T00:20:00Z
skills_applied: []
---

# Spec: Check the calling model's citations in default kb_query mode (#197)
From intent: intent/kb-cite-check.md. Status: accepted. Skills applied: (none; the two open decisions in #197 were answered by the owner at intake).

## Requirements (EARS)
Citation check tool
- R1. The MCP server shall register a tool `kb_check_citations(answer: str, context_pages: str = "") -> str` that reads no page content and writes nothing.
- R2. The tool shall parse `context_pages` by dropping one leading `context_pages:` label (case-insensitive) if present, splitting the rest on commas and whitespace, and dropping empty items.
- R3. The tool shall extract citations from `answer` with `kb.query.citations.extract_citations` and split them with `kb.query.citations.partition_citations(citations, wiki_ids=<parsed ids>, raw_ids=[], wiki_dir=<wiki dir>, raw_dir=<raw dir>)`, the two directories resolved through `kb.config` at call time.
- R4. The tool shall return, in this order: a line `Accepted (<n>): ` followed by the accepted citations comma-separated, then a line `Rejected (<m>):` followed by one line per rejected citation `  - <path> (<type>): <reason>`. `n` and `m` are always shown, `0` included.
- R5. WHEN `answer` holds no citation, the tool shall return `No citations found in answer.`
- R6. IF `answer` is empty or whitespace, or longer than `MAX_CITATION_CHECK_ANSWER_CHARS` (200_000), or the parsed ids number more than `kb.config.MAX_SEARCH_RESULTS`, THEN the tool shall return a string starting `Error: ` naming the limit, and call neither citation function.
- R7. The tool shall be listed in the `Query` group of the server instructions (`kb.mcp.app._TOOL_GROUPS`) and shall not be a long tool (`register_long_tool` is not used).

Context ids echo
- R8. WHEN default-mode `kb_query` (no `use_api`) returns pages, its response shall contain a line `context_pages: <id>, <id>, ...` listing the ids of the returned pages in the order of their `--- Page: <id>` sections, placed before the `wrap_wiki_context` fence.
- R9. WHEN default-mode `kb_query` returns pages, its response shall contain, before the fence, an instruction to call `kb_check_citations` with the answer and the `context_pages` line.
- R10. Default-mode `kb_query` paths that return no pages (empty question, no results, search error) shall return the same text as before this change.

## Design
- `kb_check_citations` lives in `src/kb/mcp/core.py` beside `kb_query`, decorated `@mcp.tool()` over `@_mcp_error_boundary` like the other `core.py` tools. It is sync and short: `partition_citations` lists the wiki or raw directory only when a citation is rejected, the same cost class as `kb_list_pages`.
- `raw_ids=[]` because the default `kb_query` context is `search_pages` results only (no raw fallback), so a raw citation is never in that context and is rejected with `out_of_context` or `nonexistent`.
- Ids are compared lower-cased inside `partition_citations` and are never passed to the filesystem, so no page-id validation is needed for R2's input.
- The echo (R8, R9) is built in `kb_query`'s default branch from the same `results` list as the page sections, after the existing header lines and before the fenced block.

## Interfaces and contracts
- New MCP tool `kb_check_citations(answer: str, context_pages: str = "") -> str` (frozen after T1-KBCITE-CHECK merges: the R2 input format is what T1-KBCITE-ECHO emits).
- Default `kb_query` response gains two lines outside the fence; the fenced wiki block is unchanged.
- `extract_citations` and `partition_citations`: unchanged.

## Data model and migration impact
none

## Flagged concerns (route to policy owners)
- (none)

## Non-goals
- A CLI command for the check.
- A server-side token binding ids to a `kb_query` response (owner decision 2).
- Rewriting the caller's answer or blocking it; the tool only reports.
- Raw-source fallback in default `kb_query`.

## Acceptance
- 1. In the `tmp_kb_env` sandbox with three pages written as bytes: an answer citing an id in `context_pages`, an existing page not in it, and a missing page returns `Accepted (1)` with the first and `Rejected (2)` with reasons `out_of_context` and `nonexistent`. [R1] [R3] [R4]
- 2. `context_pages` given as `"context_pages: a, b"`, `"a,b"` and `"a b"` accept the same citations; an upper-case citation of an in-context id is accepted. [R2] [R3]
- 3. A `[ref: raw/articles/x.md]` citation of an existing raw file is rejected `out_of_context`. [R3]
- 4. No-citation answer returns `No citations found in answer.`; empty answer, an answer of 200_001 chars and 101 ids each return `Error: ` without calling `extract_citations`. [R5] [R6]
- 5. `kb_check_citations` is registered, listed under `### Query` in `mcp.instructions`, and not in `LONG_TOOL_NAMES`; the existing tool-registration and instruction tests pass unchanged. [R7]
- 6. Default `kb_query` with stubbed `search_pages` returning two pages: the response has a `context_pages:` line with both ids in section order and a `kb_check_citations` instruction, both before `<wiki_context>`; passing that line unchanged to `kb_check_citations` with an answer citing both ids returns `Accepted (2)`. [R8] [R9]
- 7. Default `kb_query` with no results returns the same text as on main. [R10]
- 8. `README.md`, `README.zh-CN.md` and `docs/reference/mcp-servers.md` tool counts read 29 and list the tool; CHANGELOG entries per card; `CLAUDE.md` counts match `scripts/verify_docs.py`.
