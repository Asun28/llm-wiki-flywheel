---
id: T1-KBFIX-CRLFWRITERS
title: "Re-ingest, evidence appends and `kb lint --fix` write a CRLF page back with its own line ends (#175, part 2)"
status: todo
branch: T1-KBFIX-CRLFWRITERS
worktree: D:\wt\llm-wiki-flywheel\T1-KBFIX-CRLFWRITERS
plan_ref: plans/kb-fixes-2.md#order-of-work
allow_paths:
  - src/kb/ingest/pipeline.py
  - src/kb/ingest/evidence.py
  - src/kb/lint/checks/dead_links.py
  - tests/test_kbfix_crlf_writers.py
  - tests/test_ingest.py
  - tests/test_lint.py
  - docs/reference/architecture.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T1-KBFIX-CRLFWRITERS.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_crlf_writers.py tests/test_kbfix_line_ends.py tests/test_kbfix_linker_crlf.py tests/test_ingest.py tests/test_cycle24_evidence_sentinel_anchored.py tests/test_cycle24_evidence_inline_new_page.py tests/test_cycle24_evidence_error_redacted.py tests/test_cycle81_page_lock.py tests/test_cycle20_write_wiki_page_exclusive.py tests/test_backlog_by_file_cycle2.py tests/test_backlog_by_file_cycle3.py tests/test_backlog_by_file_cycle6.py tests/test_backlog_by_file_cycle7.py tests/test_fixes_v060.py tests/test_kbfix_linker_headings.py tests/test_phase45_theme3_sanitizers.py tests/test_phase45_theme4_error_handling.py tests/test_lint.py tests/test_lint_checks_split.py tests/test_lint_fix_v093.py tests/test_lint_runner.py tests/test_tier1_audit_v095.py tests/test_kbfix_code_mask_redos.py tests/test_cycle64_snapshots.py tests/test_cycle67_snapshots_negative_control.py tests/test_cycle70_snapshots.py -q
dod_exit: 0
requirements:
  - R1. The function `kb.ingest.pipeline._update_existing_page_body` shall read the page once through `read_page_text`, run every pattern on the LF text and write `restore_line_ends(content, original, ends)`.
  - R2. The function `kb.ingest.evidence.append_evidence_trail` shall read the page through `read_page_text` and write `restore_line_ends` of its edited text.
  - R3. The function `kb.lint.checks.dead_links.fix_dead_links` shall read each page through `read_page_text` and write `restore_line_ends` of its edited text, still only for a page where a link was fixed.
  - R4. WHEN a page holds no CRLF, the public writers (`_update_existing_page` with its body write and evidence append, `append_evidence_trail`, `fix_dead_links`) shall write the same bytes they wrote before this change.
  - R5. The function `_update_existing_page_body` shall turn every CRLF and lone CR in the text it inserts into LF before `restore_line_ends`, on every page.
  - R6. WHEN a page holds a CRLF, the function `append_evidence_trail` shall turn every CRLF and lone CR in the text it inserts into LF before `restore_line_ends`, so that no written line end holds a doubled CR.
acceptance:
  - 1. `test_kbfix_crlf_writers.py`: `_update_existing_page` on an all-CRLF page with `## Context` and `## References` sections, re-ingesting a new source with a context, writes a page in which every LF is preceded by CR, holding the new frontmatter `source:` entry, the new reference line, the new `### From` subsection and the new evidence entry; the page with CRLF turned to LF equals what the same call writes on the LF copy of the page. [R1] [R2] [dod arm 2]
  - 2. Same file: on an all-CRLF page, the branch that appends a fresh `## References` block and the branch that inserts a `## Context` section before `## References` each leave every line end CRLF. [R1] [dod arm 2]
  - 3. Same file: `append_evidence_trail` alone on an all-CRLF page, in each of its three branches (sentinel in the section, header without sentinel, no header), leaves every line end CRLF and inserts the entry where it does on the LF copy. [R2] [dod arm 2]
  - 4. Same file: `fix_dead_links` on an all-CRLF page with two broken links 20 lines apart replaces both and leaves every line end CRLF; a CRLF page with no broken link is not written (bytes and mtime unchanged). [R3] [dod arm 2]
  - 5. Same file: on a mixed page (CRLF on most lines, LF on one unchanged line) each writer keeps that line's LF; on an all-LF page each writer's output equals the expected bytes written out in the test. [R1] [R2] [R3] [R4] [dod arm 2]
  - 6. Every test file in the DoD passes. The only edits to existing tests are two: `tests/test_ingest.py` (`counting_read`, about line 1457), where the read-count spy moves from `Path.read_text` to `Path.read_bytes` because the page is now read as bytes and its `read_count[0] == 1` assertion is unchanged; and `tests/test_lint.py::test_atomic_text_write_patch_reaches_dead_link_fix_submodule` (about line 675), whose expected write content is computed from `page.read_bytes().decode("utf-8")` instead of `page.read_text(encoding="utf-8")`, because its fixture is written with `write_text` (CRLF on Windows) and the `read_text` expectation pinned the LF rewrite this card removes; the shared fixture `_write_pkg_const_fold_page` and every other assertion stay unchanged. The full suite passes locally on the candidate before SHIP (receipt in Attempt evidence). [R1] [dod arm 2]
  - 7. `docs/reference/architecture.md` names the three writers next to the linker as users of `kb.utils.line_ends`; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal the collected test count and test-file count on the candidate (reviewer-verified).
  - 8. `test_kbfix_crlf_writers.py`: `_update_existing_page` on an all-CRLF page, once with an extraction whose `core_argument` is `"Bread rises.\r\nBake it."` and once with a directly supplied `ctx` holding a CRLF and a lone CR, writes a page with no `"\r\r"` in its bytes and every line end CRLF, and after its evidence append has as many lines as the LF copy's output; `append_evidence_trail` with an `action` holding a CRLF on an all-CRLF page writes no `"\r\r"`; on an all-LF page the same calls write the bytes they wrote before this change (written out literally in the test). [R4] [R5] [R6] [dod arm 2]
depends_on: [T1-KBFIX-LINEENDS]
budget: 250
sweep: "Ten paths: three src writers, one new and one existing test file, four doc files and this card. `atomic_text_write` callers in src/kb (grep `atomic_text_write(`): page writers that read the page first are `ingest/pipeline.py:995` (R1), `ingest/evidence.py:250` (R2), `lint/checks/dead_links.py:115` (R3), the linker (moved in T1-KBFIX-LINEENDS) and `review/refiner.py:323` (CRLF to LF on purpose). Not page bodies: `ingest/pipeline.py:309` (contradictions), `:1044`/`:1055` (`_sources.md`), `:1109` (`index.md`), publish, augment, query formats, `utils/pages.py:256` (`frontmatter.dumps` of a Post). Existing tests that spy on `Path.read_text`: `tests/test_ingest.py:1457` changes (acceptance 6); `tests/test_cycle35_ingest_index_writers.py` spies on the `_sources.md` / `index.md` writers, which do not change; the others spy on verdicts, compiler, refiner and context readers. Missed by that grep and found by attempt 1 on Windows: `tests/test_lint.py:675` expects `fix_dead_links` to write `read_text` output of a `write_text` fixture (acceptance 6)."
forbid: [weakening an existing test, matching any pattern on text that still holds CR, releasing the page lock between the body write and the evidence append, a model call or network request in tests]
non_goals: [`refine_page` (CRLF to LF on purpose), `_update_sources_mapping` / `_update_index_batch` / the contradictions writer (kb-written LF files; 0 CRs in `wiki/index.md` and `wiki/_sources.md`), `save_page_frontmatter` (reserializes the Post), lone CR kept as CR (written as LF)]
diagnosis:
  root_cause: "The three writers read with `Path.read_text(encoding=\"utf-8\")`, whose universal-newline mode turns CRLF and lone CR into LF, and write with `atomic_text_write` (`newline=\"\\n\"`), so a CRLF page loses its line ends at the read and they are never restored. Same root cause as #168 in the linker."
  same_class: "See sweep: the linker is fixed (T0-KBFIX-CRLF, moved onto the shared helper in T1-KBFIX-LINEENDS); refiner is out of scope by design; the index, sources and contradictions writers write kb-owned LF files."
hygiene: "Run the DoD with the main checkout's `.venv` active. Branch from main after T1-KBFIX-LINEENDS merges. Write fixture pages as BYTES (`write_bytes`). SHRINK-2 lesson: run the full suite locally before SHIP. RED: the new tests fail on bare LF in the written bytes before the writers change."
doc_sync: docs/reference/architecture.md
---

# T1-KBFIX-CRLFWRITERS

## Deliverable
`_update_existing_page_body`, `append_evidence_trail` and `fix_dead_links` read pages through `kb.utils.line_ends.read_page_text` and write `restore_line_ends` of their edits, so a CRLF page keeps CRLF through re-ingest, evidence appends and `kb lint --fix`.

## Why
Issue #175: `wiki/` holds 124 CRLF pages, and each re-ingest, evidence append or `kb lint --fix` rewrites the page it touches as LF. `_update_existing_page` holds one page lock across the body write and the evidence append, and the evidence append reads the page the body write just wrote, so both writers change in this card.

## Amendment (2026-11-16, after R3 decision 2)
R3's second pass on candidate `0f4f021` (verdict `T1-KBFIX-CRLFWRITERS.r3.2.5472ed5b`, class `unnormalized-inserted-newlines`) found a defect this card introduces: a context holding `\r\n` (an extraction field keeps CR through `sanitize_extraction_field`) re-ingested into a CRLF page is written as `\r\r\n`, because `restore_line_ends` adds a CRLF after the CR the inserted text already held, and the next evidence append reads that as an extra blank line. Before this card the page was written all-LF and the defect could not occur. R5 and acceptance 8 add the fix in scope: on a CRLF page the inserting writers turn CR in the text they insert into LF before the restore. LF pages keep R4 (same bytes as before). Attempt 3 then showed that a fix conditional on the page in the body writer cannot meet R4 for `_update_existing_page`: before this card its evidence append re-read the page through `read_text`, so CR in inserted context never survived on an LF page either. R5 (body writer) therefore normalises inserted CR on every page, R6 keeps the evidence writer conditional, and R4 names the public writers; `_update_existing_page_body` called alone (its only caller is `_update_existing_page`) now writes LF where it wrote a CR from inserted context on an LF page.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_crlf_writers.py tests/test_kbfix_line_ends.py tests/test_kbfix_linker_crlf.py tests/test_ingest.py tests/test_cycle24_evidence_sentinel_anchored.py tests/test_cycle24_evidence_inline_new_page.py tests/test_cycle24_evidence_error_redacted.py tests/test_cycle81_page_lock.py tests/test_cycle20_write_wiki_page_exclusive.py tests/test_backlog_by_file_cycle2.py tests/test_backlog_by_file_cycle3.py tests/test_backlog_by_file_cycle6.py tests/test_backlog_by_file_cycle7.py tests/test_fixes_v060.py tests/test_kbfix_linker_headings.py tests/test_phase45_theme3_sanitizers.py tests/test_phase45_theme4_error_handling.py tests/test_lint.py tests/test_lint_checks_split.py tests/test_lint_fix_v093.py tests/test_lint_runner.py tests/test_tier1_audit_v095.py tests/test_kbfix_code_mask_redos.py tests/test_cycle64_snapshots.py tests/test_cycle67_snapshots_negative_control.py tests/test_cycle70_snapshots.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
