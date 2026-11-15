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

## Attempt evidence

### Attempt 1 (2026-11-16): BLOCKED, card text and an existing test disagree on Windows

- Base: origin/main `733b476`. Commits: `adc752a` (RED test), `f157ebb` (GREEN: three writers + the `counting_read` spy).
- RED (`adc752a`, src unchanged): `python -m pytest tests/test_kbfix_crlf_writers.py -q -p no:cacheprovider --tb=line` exit 1, `11 failed, 4 passed`. The 11 fail on `assert _all_crlf(written)` (lines 99, 125, 148, 187) or on the exact-bytes assert (lines 226, 341) with bare LF in the written bytes; the 4 that pass are the three LF-page byte tests (R4) and the code-only dead-link page that is not written.
- DoD (`f157ebb`, Windows, main checkout `.venv`): exit 1, `1 failed, 645 passed, 4 skipped, 3 warnings`. Failure: `tests/test_lint.py::test_atomic_text_write_patch_reaches_dead_link_fix_submodule`.
- Cause: the test writes its page with `Path.write_text`, which on Windows writes CRLF (`b'x\r\ny\r\n'`), and expects `fix_dead_links` to pass `atomic_text_write` the LF text (`page.read_text(...).replace(...)`). R3 requires that same call to pass the CRLF-restored text, so on Windows the test asserts the #175 defect; on Linux the page is LF and the test passes. The card sweep lists only the `Path.read_text` spies and missed this test. No code change satisfies both R3 and this assertion on Windows; per the card (acceptance 6) and the dispatch, the test was not edited.
- Full suite (`f157ebb`, that one test deselected): exit 0, `3876 passed, 29 skipped, 1 deselected, 17 xfailed` (3923 collected = 3908 + 15 new).
- `git diff --numstat origin/main...HEAD` before this evidence commit: `6 2 src/kb/ingest/evidence.py`, `7 7 src/kb/ingest/pipeline.py`, `5 3 src/kb/lint/checks/dead_links.py`, `2 2 tests/test_ingest.py`, `351 0 tests/test_kbfix_crlf_writers.py`.
- Not done (waits on a ruling): acceptance 7 docs (`architecture.md`, CHANGELOG entries, `CLAUDE.md` State counts).

| Acceptance | Test or command | Status |
|---|---|---|
| 1 | `test_reingest_with_context_keeps_crlf_and_matches_lf_copy` | pass |
| 2 | `test_fresh_references_block_keeps_crlf[no-references, references-header-not-matched]`, `test_context_inserted_before_references_keeps_crlf` | pass |
| 3 | `test_evidence_append_keeps_crlf_in_each_branch[3 branches]` | pass |
| 4 | `test_dead_links_fix_keeps_crlf_and_leaves_clean_page_unwritten`, `test_dead_link_only_inside_code_leaves_crlf_page_unwritten` | pass |
| 5 | `test_mixed_page_keeps_the_lf_of_an_unchanged_line[3 writers]`, `test_lf_page_is_written_with_the_same_bytes_as_before[3 writers]` | pass |
| 6 | DoD | FAIL: `test_lint.py::test_atomic_text_write_patch_reaches_dead_link_fix_submodule` (Windows only) |
| 7 | docs | not started |

### Attempt 2 (2026-11-16): card amended on main (f64df69), DoD and full suite green

- Base sync: merge `5979da6` (origin/main `f64df69` into the branch; no conflict, attempt-1 evidence kept). No rebase or amend.
- Commits: `07e2352` (`tests/test_lint.py::test_atomic_text_write_patch_reaches_dead_link_fix_submodule`: expected write computed from `page.read_bytes().decode("utf-8")` instead of `page.read_text(encoding="utf-8")`; fixture `_write_pkg_const_fold_page` and every other assertion unchanged), `a7474e4` (docs). Src unchanged since `f157ebb`.
- DoD (`a7474e4`, Windows, main checkout `.venv`, command exactly as in the card): exit 0. `ruff check src/ tests/`: `All checks passed!`; pytest: `646 passed, 4 skipped, 3 warnings in 44.15s`; `6 snapshots passed.`
- Full suite (`a7474e4`, `python -m pytest -q -p no:cacheprovider`, nothing deselected): exit 0, `3877 passed, 29 skipped, 17 xfailed, 54 warnings in 258.35s` (3923 collected).
- `scripts/verify_docs.py` (`a7474e4`): `pytest collected tests = 3923`, `test file count = 224`, `OK - docs in sync`.
- `git diff --numstat origin/main...HEAD` (`a7474e4`): `11 0 CHANGELOG-history.md`, `1 0 CHANGELOG.md`, `1 1 CLAUDE.md`, `1 1 docs/reference/architecture.md`, `22 0 specs/tasks/T1-KBFIX-CRLFWRITERS.md`, `6 2 src/kb/ingest/evidence.py`, `7 7 src/kb/ingest/pipeline.py`, `5 3 src/kb/lint/checks/dead_links.py`, `2 2 tests/test_ingest.py`, `351 0 tests/test_kbfix_crlf_writers.py`, `1 1 tests/test_lint.py`.
- Follow-up note (not changed, outside this card): the comment at `src/kb/ingest/pipeline.py:996` says `append_evidence_trail` "acquires its own `file_lock(page_path)`"; since cycle 81 it re-enters `page_lock`.

| Acceptance | Test or command | Status |
|---|---|---|
| 1 | `test_reingest_with_context_keeps_crlf_and_matches_lf_copy` | pass |
| 2 | `test_fresh_references_block_keeps_crlf[no-references, references-header-not-matched]`, `test_context_inserted_before_references_keeps_crlf` | pass |
| 3 | `test_evidence_append_keeps_crlf_in_each_branch[sentinel-in-section, header-without-sentinel, no-header]` | pass |
| 4 | `test_dead_links_fix_keeps_crlf_and_leaves_clean_page_unwritten`, `test_dead_link_only_inside_code_leaves_crlf_page_unwritten` | pass |
| 5 | `test_mixed_page_keeps_the_lf_of_an_unchanged_line[ingest-body, evidence, dead-links]`, `test_lf_page_is_written_with_the_same_bytes_as_before[ingest-body, evidence, dead-links]` | pass |
| 6 | DoD exit 0; full suite exit 0; existing-test edits limited to `tests/test_ingest.py` (`counting_read` spy) and `tests/test_lint.py` (one expected-value line) | pass |
| 7 | `docs/reference/architecture.md` (three writers named next to the linker), `CHANGELOG.md` and `CHANGELOG-history.md` (one entry each), `CLAUDE.md` State `3923 tests across 224 test files` = `verify_docs.py` | pass (reviewer to verify) |

### Attempt 3 (2026-11-16): BLOCKED, acceptance 8's LF case conflicts with a conditional R5 in the body writer

- Base sync: merge `42a3da5` (origin/main `6b279c5`, card amendment R5 + acceptance 8; no conflict).
- RED `e378b83` (acceptance 8 tests, src at `0f4f021`): exit 1, `5 failed, 16 passed`. CRLF page, extraction and direct ctx: `_all_crlf` fails (line 437; the evidence append re-read the doubled CR as an extra LF line). LF page, extraction and direct ctx: bytes differ from the pre-card bytes (line 450; the CRLF from the context survives). CRLF page, evidence action: `b"\r\r"` found (line 463). LF page, evidence action: passes (pre-card bytes). The three LF-page expectations were checked against `733b476`'s src (`-o pythonpath=<733b476 src copy>`): `3 passed`.
- Fix `d46bc32` (as instructed: both writers turn CRLF and lone CR into LF only when the page's `line_ends` hold a CRLF): DoD exit 1, `2 failed, 650 passed, 4 skipped`; failing: `test_cr_in_inserted_context_on_lf_page_writes_the_bytes_of_before[extraction]` and `[direct-ctx]`.
- Cause: on an all-LF page the body write keeps the inserted `\r\n` (R4 for the body writer), and the evidence append that `_update_existing_page` runs next then reads a page that holds a CRLF, so `restore_line_ends` keeps that line's CRLF. Before this card the evidence append's `read_text` turned every CR into LF, so the composed call wrote an all-LF page. A condition evaluated per writer cannot give the composed call the pre-card bytes on an LF page; acceptance 8's LF case and a conditional body writer conflict.
- Measured alternative, not committed: the body writer normalises inserted CR unconditionally, while the evidence writer stays conditional. On a scratch copy of `d46bc32`'s src, `test_kbfix_crlf_writers.py`, `test_ingest.py`, `test_cycle24_evidence_sentinel_anchored.py` and `test_cycle81_page_lock.py` gave `195 passed`. Trade-off: `_update_existing_page_body` alone on an LF page with CR in the inserted context then writes LF where it wrote CR before (R4 literal), which persists only if the following evidence append fails; its only caller is `_update_existing_page`.
- Follow-up note (outside this card): the comment at `src/kb/ingest/pipeline.py` after the body write says `append_evidence_trail` "acquires its own `file_lock(page_path)`"; since cycle 81 it re-enters `page_lock`.

#### Attempt 3, resumed: paused at `d46bc32` for an owner-side contract ruling, resumed after `e89c9dc` (option A)

- Base sync: merge `f5f013c` (origin/main `e89c9dc`: R4 names the public writers, R5 body writer on every page, R6 evidence writer on CRLF pages; no conflict).
- Commits: `37cecd3` (`_update_existing_page_body` drops the `if "\r\n" in line_ends:` guard and turns inserted CRLF and lone CR into LF on every page; comment updated; `append_evidence_trail` keeps its guard), `23db60b` (docs: R5/R6 wording in `architecture.md`, `CHANGELOG.md`, `CHANGELOG-history.md`; `CLAUDE.md` State `3929 tests across 224 test files`; `scripts/verify_docs.py`: collected 3929, files 224, `OK - docs in sync`).
- DoD (`23db60b`, Windows, main checkout `.venv`, command exactly as in the card): exit 0. `ruff check src/ tests/`: `All checks passed!`; pytest: `652 passed, 4 skipped, 3 warnings in 43.72s`; `6 snapshots passed.`
- Full suite (`23db60b`, `python -m pytest -q -p no:cacheprovider`, nothing deselected): exit 0, `3883 passed, 29 skipped, 17 xfailed, 54 warnings in 455.42s` (3929 collected).
- `git diff --numstat origin/main...HEAD` (`23db60b`): `12 0 CHANGELOG-history.md`, `1 0 CHANGELOG.md`, `1 1 CLAUDE.md`, `1 1 docs/reference/architecture.md`, `51 0 specs/tasks/T1-KBFIX-CRLFWRITERS.md`, `10 2 src/kb/ingest/evidence.py`, `12 7 src/kb/ingest/pipeline.py`, `5 3 src/kb/lint/checks/dead_links.py`, `2 2 tests/test_ingest.py`, `479 0 tests/test_kbfix_crlf_writers.py`, `1 1 tests/test_lint.py`.
- Follow-up note (unchanged, outside this card): the comment after the body write in `src/kb/ingest/pipeline.py` says `append_evidence_trail` "acquires its own `file_lock(page_path)`"; since cycle 81 it re-enters `page_lock`.

| Acceptance | Test or command | Status |
|---|---|---|
| 1 | `test_reingest_with_context_keeps_crlf_and_matches_lf_copy` | pass |
| 2 | `test_fresh_references_block_keeps_crlf[no-references, references-header-not-matched]`, `test_context_inserted_before_references_keeps_crlf` | pass |
| 3 | `test_evidence_append_keeps_crlf_in_each_branch[sentinel-in-section, header-without-sentinel, no-header]` | pass |
| 4 | `test_dead_links_fix_keeps_crlf_and_leaves_clean_page_unwritten`, `test_dead_link_only_inside_code_leaves_crlf_page_unwritten` | pass |
| 5 | `test_mixed_page_keeps_the_lf_of_an_unchanged_line[ingest-body, evidence, dead-links]`, `test_lf_page_is_written_with_the_same_bytes_as_before[ingest-body, evidence, dead-links]` | pass |
| 6 | DoD exit 0; full suite exit 0; existing-test edits limited to `tests/test_ingest.py` (`counting_read` spy) and `tests/test_lint.py` (one expected-value line) | pass |
| 7 | `architecture.md` (three writers next to the linker, inserted-CR rule), one entry each in `CHANGELOG.md` and `CHANGELOG-history.md`, `CLAUDE.md` State `3929 tests across 224 test files` = `verify_docs.py` | pass (reviewer to verify) |
| 8 | `test_cr_in_inserted_context_is_written_crlf_on_crlf_page[extraction, direct-ctx]`, `test_cr_in_inserted_context_on_lf_page_writes_the_bytes_of_before[extraction, direct-ctx]`, `test_cr_in_evidence_action_is_written_crlf_on_crlf_page`, `test_cr_in_evidence_action_on_lf_page_writes_the_bytes_of_before` (RED `e378b83`: 5 failed, 1 passed) | pass |
