---
slug: kb-defects-1
title: Fix four product defects the knowledge-layer baseline found (#154, #160, #161, #162)
intent: intent/kb-defects-1.md
status: accepted
created: 2026-11-15T06:20:00Z
skills_applied: [grilling]
---

# Spec: Fix four product defects the knowledge-layer baseline found (#154, #160, #161, #162)
From intent: intent/kb-defects-1.md. Status: accepted. Skills applied: grilling (one round, four owner decisions).

## Requirements (EARS)
Vector index stored dimension (#154)
- R1. WHEN the `vec_pages` table exists, `VectorIndex._read_stored_dim` shall return the `N` of `float[N]` in that table's declaration in `sqlite_master.sql`, independent of what `PRAGMA table_info` reports.
- R2. IF the `vec_pages` table does not exist, THEN `_read_stored_dim` shall return 0.
- R3. IF the `vec_pages` table exists and no `float[N]` can be read from its declaration, THEN `_read_stored_dim` shall return 0 and `VectorIndex` shall log one WARNING per instance naming the database path.
- R4. WHEN an index is built with the installed `sqlite_vec` extension and queried with a vector of the built dimension, `VectorIndex.query` shall return at least one hit.

Template baseline on ingest (#160)
- R5. WHEN `ingest_source` commits a source hash to the manifest, it shall, in the same `file_lock(HASH_MANIFEST)` span, write `_template/<source_type>` with the current hash of `templates/<source_type>.yaml` IF AND ONLY IF that key is absent and the template exists. [SOURCE: owner decision 2026-11-15]
- R6. `ingest_source` shall never overwrite an existing `_template/<source_type>` value.
- R7. WHEN a wiki is built by `ingest_source` alone and nothing has changed since, `find_changed_sources(raw_dir, manifest, save_hashes=False)` shall return no source.

Wikilinks in headings (#161)
- R8. WHEN ingest appends a `### From <source_ref>` subsection, the source ref shall be written as a CommonMark inline code span. [SOURCE: owner decision 2026-11-15]
- R9. `inject_wikilinks` and `inject_wikilinks_batch` shall not insert a wikilink inside an ATX heading line (0-3 spaces, 1-6 `#`, then a space, a tab or the end of the line), in the pre-lock peek and in the locked rewrite. [SOURCE: owner decision 2026-11-15]
- R10. The behaviour of `_mask_code_blocks` for its other callers (ingest Context/References editing, the dead-links lint) shall be unchanged.

Refine shrink guard (#162)
- R11. IF the stripped new body of `refine_page` has fewer than half the characters of the stripped current body, and `allow_shrink` is not true, THEN `refine_page` shall refuse the write and return an `error` that states both lengths and the ratio, with the page and the review history unchanged. [SOURCE: owner decision 2026-11-15: 50% floor]
- R12. WHEN `allow_shrink=True` is passed and the floor of R11 is crossed, `refine_page` shall write the page and record `allow_shrink: true` with both lengths in that attempt's review-history row. [SOURCE: owner decision 2026-11-15: explicit override recorded in history]
- R13. The MCP tool `kb_refine_page` shall accept `allow_shrink` (default false) and pass it to `refine_page`.

## Design
Four independent fixes in four modules; no shared new interface.

- `kb.query.embeddings.VectorIndex._read_stored_dim`: read `SELECT sql FROM sqlite_master WHERE type='table' AND name='vec_pages'`, parse `float\[(\d+)\]`. No row -> 0 (missing table). A row without a parseable dim -> 0 plus a once-per-instance WARNING (R3). The existing dim-mismatch and auto-rebuild path is untouched.
- `kb.ingest.pipeline._commit_ingest_manifest` gains the source type and calls `kb.compile.compiler._template_hashes()` (lazy import, as the module already does for `load_manifest`) inside its existing `file_lock` span; `setdefault`-style write. `find_changed_sources` is not changed.
- `kb.ingest.pipeline` writes ``### From `raw/...` ``; a ref containing a backtick uses a longer backtick delimiter with space padding so the span stays one code span.
- `kb.compile.linker`: a heading mask applied only in the injection paths, on top of `_mask_code_blocks`, sharing its placeholder list and prefix so `_unmask_code_blocks` restores it. `_mask_code_blocks` itself keeps its contract: an experiment that masked headings inside it broke 5 ingest tests (Context/References editing in `_update_existing_page`).
- `kb.review.refiner.refine_page(..., allow_shrink: bool = False)`: the floor check runs after the frontmatter gates and the empty-body guard, before the pending history row. Lengths are counted after CRLF->LF and `strip()`. The ratio constant lives in `kb.config` (`REFINE_MIN_BODY_RATIO = 0.5`). A current body of length 0 has no floor.

## Interfaces and contracts
- `refine_page(page_id, updated_content, revision_notes="", wiki_dir=None, history_path=None, *, allow_shrink=False)` (new keyword-only argument; existing positional calls unchanged).
- `kb_refine_page(page_id, updated_content, revision_notes="", allow_shrink=False)`.
- Review-history row: optional keys `allow_shrink`, `previous_body_length`, `new_body_length`, present only on an override write (absence = no override, per the cycle-73/88 absence convention).
- Manifest: `_template/<type>` may now be written by ingest (only when absent).
- No frozen contract changes.

## Data model and migration impact
None. Existing wikis keep working: an ingest-only wiki without `_template/` keys gets them on its next ingest of that source type or its next `compile_wiki`; until then the scan stays conservative (lists the sources), as today. Pages already holding a bare `### From raw/...` heading are protected by R9 without rewriting them.

## Flagged concerns (route to policy owners)
- (none)

## Non-goals
- Setext headings (`Title` underlined with `===`/`---`) in the linker mask: wiki pages use ATX headings.
- Rewriting existing `### From` headings to inline code.
- `KB_DISABLE_VECTORS` not applying to `search_pages` (related finding in #154): separate defect, left open.
- `find_changed_sources` behaviour for a missing `_template/` key.
- A CLI command for refine.
- Rewriting the committed Phase 0 baseline (`bench/knowledge/summary.json`, `docs/knowledge-baseline.md`).
- Bench-tool issues #163, #157, #148.

## Acceptance
- 1. A test against the real `sqlite_vec` extension builds an index and gets at least one hit from `VectorIndex.query`; a declaration without a dim returns 0 and logs once. [R1-R4]
- 2. A test ingests sources with a supplied extraction and gets an empty list from `find_changed_sources(..., save_hashes=False)`; a compile-written `_template/` value survives a later ingest and still flags the type. [R5-R7]
- 3. A test ingests a re-ingest context into a page and the heading is inline code; linking a page whose `### From raw/articles/high-hydration.md` heading contains a title leaves the heading byte-identical while the body still gets the link; the existing ingest Context/References tests pass. [R8-R10]
- 4. Tests on both sides of the 50% floor, an override write with its history row, and the MCP pass-through. [R11-R13]
- 5. Integrated: the full test suite and `bench/knowledge/tests` pass on the final SHA, and a bench rerun to a scratch directory reports `rebuild.scan` measured with `listed_clean` 0, `provenance.refine` refusing the 10% and 1% bodies, and the `retrieval` hybrid arm measured or unmeasured for a reason other than an empty vector branch. [R4] [R7] [R11]
