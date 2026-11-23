---
slug: kb-cite-check
title: "Check the calling model's citations in default kb_query mode (#197)"
author: asun28 (engineer)
status: accepted
created: 2026-11-23T00:03:22Z
source: human
---

# Intent: Check the calling model's citations in default kb_query mode (#197)
Author: asun28 (engineer). Status: accepted.

## Problem
#189 (card T0-KBFIX-CITECTX, PR #198) made `query_wiki` keep only citations
whose id was in the prompt and return the rest under `rejected_citations`.
The default MCP mode skips that check: `kb_query` without `use_api` returns
the wiki context and the calling model writes the answer
(`src/kb/mcp/core.py`). No answer reaches `query_wiki`, so nothing compares
the caller's citations with the pages it was given. A caller can cite a page
it never saw, or one that does not exist, and nothing reports it.

## Proposed outcome
- After writing an answer from `kb_query`'s default context, the calling model
  can pass the answer and the page ids it was given to one MCP tool and get
  back the accepted citations and the rejected ones, each with the reason
  (`out_of_context` or `nonexistent`) that `partition_citations` gives.
- The default `kb_query` response states the ids of the pages in its context
  in a form the caller can pass back unchanged.
- #197 is closed with a comment naming the merged PRs.

## Affected users and systems
- `src/kb/mcp/core.py` (`kb_query` default branch; the new tool),
  `src/kb/mcp/app.py` (tool group listing).
- Docs listing the MCP tools: `README.md`, `README.zh-CN.md`,
  `docs/reference/mcp-servers.md`.
- Users: Claude Code (or any MCP client) answering from `kb_query`.

## Constraints
- Development target only.
- `kb.query.citations.extract_citations` and `partition_citations` are reused
  unchanged.
- No existing test is edited.
- The ids line sits outside the `wrap_wiki_context` fence (cycle-70 rule:
  instructions to the caller outside, wiki content inside).

## Decisions (owner, 2026-11-23)
1. A new MCP tool, not a parameter on `kb_query`.
2. `kb_query` echoes the context page ids in its response and the caller
   passes them back; no server-side token.

## Open questions
- (none)
