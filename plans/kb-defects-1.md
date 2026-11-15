---
slug: kb-defects-1
title: Fix four product defects the knowledge-layer baseline found (#154, #160, #161, #162)
spec: specs/kb-defects-1.md
size: T1
status: accepted
created: 2026-11-15T06:25:00Z
---

# Plan: Fix four product defects the knowledge-layer baseline found (from specs/kb-defects-1.md)

## 1. Goal and boundaries
Fix #154, #160, #161 and #162 in `src/kb/` with a reproducing test for each, under the owner decisions in `intent/kb-defects-1.md`. Cut: bench-tool issues #163, #157, #148; the `KB_DISABLE_VECTORS` / `search_pages` gap; rewriting the committed Phase 0 baseline. Success: spec acceptance 1-5 on the final integrated SHA.

## 2. Minimal acceptable loop
One card per issue: RED test reproducing the defect, the fix, GREEN, R3 review, merge. Then VERIFY-ARC: full suite, `bench/knowledge/tests`, and a bench rerun into a scratch directory.

## 3. Tech stack
none this version

## 4. Directory structure
none this version (new test files only, one per card)

## 4.5 Module design
- `kb.query.embeddings` (VECDIM): stored dim read from `sqlite_master.sql`.
- `kb.ingest.pipeline` (TPLBASE): manifest commit also writes a missing `_template/<type>`.
- `kb.ingest.pipeline` + `kb.compile.linker` (FROMHEAD): inline-code source ref; heading mask on the injection path only.
- `kb.review.refiner` + `kb.mcp.quality` + `kb.config` (SHRINK): 50% floor and `allow_shrink`.

## 5. Data model and state machine
none this version (manifest gains ingest-written `_template/` keys only when absent; review-history rows gain optional override keys)

## 6. Contracts and core interfaces
`refine_page(..., *, allow_shrink=False)` and `kb_refine_page(..., allow_shrink=False)`; no frozen contract changes. See spec "Interfaces and contracts".

## Files that change
- src/kb/query/embeddings.py
- src/kb/ingest/pipeline.py
- src/kb/compile/linker.py
- src/kb/review/refiner.py
- src/kb/mcp/quality.py
- src/kb/config.py
- tests/test_kbfix_vector_stored_dim.py (new)
- tests/test_kbfix_ingest_template_baseline.py (new)
- tests/test_kbfix_linker_headings.py (new)
- tests/test_kbfix_refine_shrink_guard.py (new)
- CHANGELOG.md, CHANGELOG-history.md, CLAUDE.md (test counts), BACKLOG.md (#162 entry deleted), docs/reference/architecture.md, docs/reference/mcp-servers.md

## Order of work
1. T1-KBFIX-VECDIM: real-extension RED test, then read the dim from `sqlite_master.sql`.
2. T1-KBFIX-TPLBASE: ingest-then-scan RED test, then the absent-only `_template/` write in `_commit_ingest_manifest`.
3. T1-KBFIX-FROMHEAD (after TPLBASE: both edit `src/kb/ingest/pipeline.py`): heading RED tests, then inline-code heading and the injection-only heading mask.
4. T1-KBFIX-SHRINK: floor RED tests, then the guard, the override and the MCP argument.
5. VERIFY-ARC on the final SHA.

## 7. Task split (dependencies and parallel windows)

| Card | Priority | Output | depends_on | Parallel window | Freeze point |
|---|---|---|---|---|---|
| T1-KBFIX-VECDIM | MUST | vector query returns hits with sqlite-vec 0.1.9 | - | - | - |
| T1-KBFIX-TPLBASE | MUST | ingest-only wiki scans clean | - | - | - |
| T1-KBFIX-FROMHEAD | MUST | no wikilink inside a heading | T1-KBFIX-TPLBASE | - | - |
| T1-KBFIX-SHRINK | MUST | refine refuses a body under 50% without `allow_shrink` | - | - | - |

All four cards share `CHANGELOG.md`, `CHANGELOG-history.md` and `CLAUDE.md`, so they run one at a time (no parallel window).

## Risks
- `_mask_code_blocks` is shared with ingest and the dead-links lint: masking headings inside it broke 5 ingest tests in a pre-plan experiment. FROMHEAD masks headings on the injection path only (spec R10).
- The 50% floor could break existing refine tests: a read-only probe over the 19 test files that call `refine_page` (595 passed) found one call under 50% (`tests/test_fixes_v050.py::test_refine_page_invalid_frontmatter`), which is refused earlier by the frontmatter gate. Placing the floor after the frontmatter gates keeps it unchanged.
- An ingest after a template edit must not hide the edit from the scan: TPLBASE writes `_template/<type>` only when absent (owner decision).
- The real `sqlite_vec` test depends on the `hybrid` extra; CI installs it (`.[dev,formats,augment,hybrid,eval]`).

## Proof
- Per card: its `dod_command` (ruff + new test file + the existing test files of the touched module), RED receipt before the fix.
- Arc: `python -m pytest -q`, `python -m pytest bench/knowledge/tests -q`, and `python bench/knowledge/run.py --out <scratch>` with the three arm values compared to the Phase 0 baseline.

## 10. After merge
none this version (development-only target). Each closed issue gets a comment with the bench numbers from VERIFY-ARC.
