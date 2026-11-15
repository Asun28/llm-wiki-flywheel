---
slug: kb-defects-1
title: Fix four product defects the knowledge-layer baseline found (#154, #160, #161, #162)
author: asun28 (engineer)
status: accepted
created: 2026-11-15T06:00:00Z
source: human
---

# Intent: Fix four product defects the knowledge-layer baseline found (#154, #160, #161, #162)
Author: asun28 (engineer). Status: accepted.

## Problem
The Phase 0 knowledge-layer baseline (`docs/knowledge-baseline.md`, goal
kb-baseline) filed four defects in the `kb` package. Each one either turns a
feature off without a warning or lets one call damage wiki content:

1. #154: `VectorIndex._read_stored_dim` parses the embedding dimension from the
   `type` column of `PRAGMA table_info(vec_pages)`. With sqlite-vec 0.1.9 that
   column is empty for a `vec0` table, so the dimension reads as 0 and
   `VectorIndex.query` returns `[]` for every query with no log line. Hybrid
   search is BM25-only in practice.
2. #160: `ingest_source` records only `manifest[source_ref]`. The
   `_template/<type>` keys are written only by `compile_wiki`, so on a wiki
   built by ingest alone `find_changed_sources` reads every missing key as a
   template change and lists every source as changed.
3. #161: `inject_wikilinks` inserts a wikilink inside the bare source path of
   a `### From raw/...` heading (seen: `### From raw/articles/high-[[concepts/hydration|Hydration]].md`),
   so the path in the heading is no longer valid.
4. #162: `refine_page` refuses only an empty body. A replacement body that
   keeps 1% of the page is accepted with no warning, and the call is
   reachable from the `kb_refine_page` MCP tool.

## Proposed outcome
- Vector search returns hits on an index built with the installed sqlite-vec,
  and a test against the real `sqlite_vec` extension fails if the stored-dim
  format changes again. A built index that reports dimension 0 is logged once.
- Ingest, then scan with nothing changed: `find_changed_sources` returns an
  empty list.
- After ingest and linking, no `### From` heading contains a wikilink, on new
  and on already-written pages.
- `refine_page` refuses a body under the shrink floor unless the caller passes
  an explicit override, and the override is recorded in the review history.
- The knowledge bench arms that these defects blocked (`retrieval` hybrid,
  `rebuild.scan`, `provenance.refine`) are rerun into a scratch directory and
  the new numbers are recorded in the arc evidence and on each closed issue.
  The committed Phase 0 baseline stays as the before-reference.

## Affected users and systems
- `src/kb/query/embeddings.py` (vector index), `src/kb/compile/compiler.py`
  and `src/kb/ingest/pipeline.py` (manifest), `src/kb/compile/linker.py` and
  `src/kb/ingest/pipeline.py` (wikilinks), `src/kb/review/refiner.py` and
  `src/kb/mcp/quality.py` (refine).
- Users: anyone running `kb query` / `kb_query` (vector branch), `kb compile`
  after ingest, and the MCP `kb_refine_page` tool.

## Constraints
- Development target only. No release, no data migration of existing wikis.
- Existing tests must not be weakened; behaviour changes are pinned by new tests.
- Owner rulings below are binding for the spec.

## Decisions (owner, 2026-11-15)
The owner took the recommended answer to each of the four intake questions.
- #162 shrink rule: refuse a new body under **50%** of the current body length;
  the error returns both lengths and the ratio. An explicit `allow_shrink=True`
  argument passes the guard and is recorded in the review history.
- #161 linker: ingest writes new headings as ``### From `raw/...` `` (inline
  code), **and** the linker masks all ATX heading lines, so pages already
  written are covered and `[[page#Heading]]` anchors stay stable.
- #160 baseline: `ingest_source` writes `_template/<type>` **only when the key
  is missing**, in the same locked manifest commit as the source hash. A
  baseline written by `compile_wiki` is never overwritten, so a template edit
  since the last compile still flags old pages.
- Scope: these four issues only. Bench-tool issues #163, #157, #148 stay open.

## Open questions
- (none)
