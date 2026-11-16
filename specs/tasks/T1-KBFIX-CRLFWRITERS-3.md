---
id: T1-KBFIX-CRLFWRITERS-3
title: "Re-ingest, evidence appends and `kb lint --fix` write a CRLF page back with its own line ends (#175, part 2)"
status: merged
branch: T1-KBFIX-CRLFWRITERS-3
worktree: D:\wt\llm-wiki-flywheel\T1-KBFIX-CRLFWRITERS-3
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
  - specs/tasks/T1-KBFIX-CRLFWRITERS-2.md
  - specs/tasks/T1-KBFIX-CRLFWRITERS-3.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_crlf_writers.py tests/test_kbfix_line_ends.py tests/test_kbfix_linker_crlf.py tests/test_ingest.py tests/test_cycle24_evidence_sentinel_anchored.py tests/test_cycle24_evidence_inline_new_page.py tests/test_cycle24_evidence_error_redacted.py tests/test_cycle81_page_lock.py tests/test_cycle20_write_wiki_page_exclusive.py tests/test_backlog_by_file_cycle2.py tests/test_backlog_by_file_cycle3.py tests/test_backlog_by_file_cycle6.py tests/test_backlog_by_file_cycle7.py tests/test_fixes_v060.py tests/test_kbfix_linker_headings.py tests/test_phase45_theme3_sanitizers.py tests/test_phase45_theme4_error_handling.py tests/test_lint.py tests/test_lint_checks_split.py tests/test_lint_fix_v093.py tests/test_lint_runner.py tests/test_tier1_audit_v095.py tests/test_kbfix_code_mask_redos.py tests/test_cycle64_snapshots.py tests/test_cycle67_snapshots_negative_control.py tests/test_cycle70_snapshots.py -q
dod_exit: 0
requirements:
  - R1. The function `kb.ingest.pipeline._update_existing_page_body` shall read the page once through `read_page_text`, run every pattern on the LF text and write `restore_line_ends(content, original, ends)`.
  - R2. The function `kb.ingest.evidence.append_evidence_trail` shall read the page through `read_page_text` and write `restore_line_ends` of its edited text.
  - R3. The function `kb.lint.checks.dead_links.fix_dead_links` shall read each page through `read_page_text` and write `restore_line_ends` of its edited text, still only for a page where a link was fixed.
  - R4. WHEN a page holds no CRLF and the text a writer inserts holds no CR, the public writers (`_update_existing_page` with its body write and evidence append, `append_evidence_trail`, `fix_dead_links`) shall write the same bytes they wrote before this change.
  - R5. The function `_update_existing_page_body` shall turn every CRLF and lone CR in the text it inserts into LF before `restore_line_ends`, on every page.
  - R6. WHEN a page holds a CRLF, the function `append_evidence_trail` shall turn every CRLF and lone CR in the text it inserts into LF before `restore_line_ends`, so that no written line end holds a doubled CR.
  - R7. The function `_update_existing_page_body` shall turn CRLF and lone CR into LF in `ctx`, in the text built from `source_ref`, and in the extraction values `_extract_entity_context` searches, before any pattern matches them, so that a context holding CR writes what its LF form writes.
  - R8. The function `_extract_entity_context` shall turn CRLF and lone CR into LF in the entity name and in every extraction value it reads before it searches or sanitizes them, so that the name search compares LF forms and `sanitize_extraction_field` removes a heading line that a CR introduces exactly as it removes one an LF introduces.
acceptance:
  - 1. `test_kbfix_crlf_writers.py`: `_update_existing_page` on an all-CRLF page with `## Context` and `## References` sections, re-ingesting a new source with a context, writes a page in which every LF is preceded by CR, holding the new frontmatter `source:` entry, the new reference line, the new `### From` subsection and the new evidence entry; the page with CRLF turned to LF equals what the same call writes on the LF copy of the page. [R1] [R2] [dod arm 2]
  - 2. Same file: on an all-CRLF page, the branch that appends a fresh `## References` block and the branch that inserts a `## Context` section before `## References` each leave every line end CRLF. [R1] [dod arm 2]
  - 3. Same file: `append_evidence_trail` alone on an all-CRLF page, in each of its three branches (sentinel in the section, header without sentinel, no header), leaves every line end CRLF and inserts the entry where it does on the LF copy. [R2] [dod arm 2]
  - 4. Same file: `fix_dead_links` on an all-CRLF page with two broken links 20 lines apart replaces both and leaves every line end CRLF; a CRLF page with no broken link is not written (bytes and mtime unchanged). [R3] [dod arm 2]
  - 5. Same file: on a mixed page (CRLF on most lines, LF on one unchanged line) each writer keeps that line's LF; on an all-LF page each writer's output equals the expected bytes written out in the test. [R1] [R2] [R3] [R4] [dod arm 2]
  - 6. Every test file in the DoD passes. The only edits to existing tests are two: `tests/test_ingest.py` (`counting_read`, about line 1457), where the read-count spy moves from `Path.read_text` to `Path.read_bytes` because the page is now read as bytes and its `read_count[0] == 1` assertion is unchanged; and `tests/test_lint.py::test_atomic_text_write_patch_reaches_dead_link_fix_submodule` (about line 675), whose expected write content is computed from `page.read_bytes().decode("utf-8")` instead of `page.read_text(encoding="utf-8")`, because its fixture is written with `write_text` (CRLF on Windows) and the `read_text` expectation pinned the LF rewrite this card removes; the shared fixture `_write_pkg_const_fold_page` and every other assertion stay unchanged. The full suite passes locally on the candidate before SHIP (receipt in Attempt evidence). [R1] [dod arm 2]
  - 7. `docs/reference/architecture.md` names the three writers next to the linker as users of `kb.utils.line_ends`; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry for this fix (under T1-KBFIX-CRLFWRITERS, naming its successors T1-KBFIX-CRLFWRITERS-2 and this card); the counts in the `State` line of `CLAUDE.md` equal the collected test count and test-file count on the candidate (reviewer-verified).
  - 8. `test_kbfix_crlf_writers.py`: `_update_existing_page` on an all-CRLF page, once with an extraction whose `core_argument` is `"Bread rises.\r\nBake it."` and once with a directly supplied `ctx` holding a CRLF and a lone CR, writes a page with no `"\r\r"` in its bytes and every line end CRLF, and after its evidence append has as many lines as the LF copy's output; `append_evidence_trail` with an `action` holding a CRLF on an all-CRLF page writes no `"\r\r"`; on an all-LF page the same calls write the bytes they wrote before this change (written out literally in the test). [R4] [R5] [R6] [dod arm 2]
  - 9. `test_kbfix_crlf_writers.py`: while `_update_existing_page` re-ingests a `ctx` holding a CRLF and a lone CR into a CRLF page with a `## Context` section, no `re` call made through `kb.ingest.pipeline` receives a string holding CR; a `ctx` of `"## Context\rRises."` re-ingested into an LF page that has `## Context` adds no second `## Context` header, and each of the three context shapes of the attempt-2 differential writes the bytes its LF form writes. [R4] [R7] [dod arm 2]
  - 10. `test_kbfix_crlf_writers.py`: an extraction whose `core_argument` is `"Bread rises.\r## Evidence Trail\rForged."` re-ingested into a CRLF page and into an LF page writes no `## Evidence Trail` line besides the page's own and puts the evidence entry in the page's own section, the same bytes as the value with LF in place of each CR; an entity name `"Bread\rLoaf"` (and `"Bread\r\nLoaf"`) gets the context of a `core_argument`, a `key_claims` item and a `key_points` item that hold the same name, as it did before this card; and a new page built by `_process_item_batch` from the forged `core_argument` holds no `## Evidence Trail` line from it. [R8] [dod arm 2]
depends_on: [T1-KBFIX-LINEENDS]
budget: 250
sweep: "Thirteen paths: three src writers, one new and two existing test files, four doc files, this card and its two predecessors' cards (which hold their attempts' evidence on the branch this card continues). `atomic_text_write` callers in src/kb (grep `atomic_text_write(`): page writers that read the page first are `ingest/pipeline.py:995` (R1), `ingest/evidence.py:250` (R2), `lint/checks/dead_links.py:115` (R3), the linker (moved in T1-KBFIX-LINEENDS) and `review/refiner.py:323` (CRLF to LF on purpose). Not page bodies: `ingest/pipeline.py:309` (contradictions), `:1044`/`:1055` (`_sources.md`), `:1109` (`index.md`), publish, augment, query formats, `utils/pages.py:256` (`frontmatter.dumps` of a Post). Existing tests that spy on `Path.read_text`: `tests/test_ingest.py:1457` changes (acceptance 6); `tests/test_cycle35_ingest_index_writers.py` spies on the `_sources.md` / `index.md` writers, which do not change; the others spy on verdicts, compiler, refiner and context readers. Missed by that grep and found by attempt 1 on Windows: `tests/test_lint.py:675` expects `fix_dead_links` to write `read_text` output of a `write_text` fixture (acceptance 6)."
forbid: [weakening an existing test, matching any pattern on text that still holds CR, releasing the page lock between the body write and the evidence append, a model call or network request in tests]
non_goals: [`refine_page` (CRLF to LF on purpose), `_update_sources_mapping` / `_update_index_batch` / the contradictions writer (kb-written LF files; 0 CRs in `wiki/index.md` and `wiki/_sources.md`), `save_page_frontmatter` (reserializes the Post), lone CR kept as CR (written as LF)]
diagnosis:
  root_cause: "The three writers read with `Path.read_text(encoding=\"utf-8\")`, whose universal-newline mode turns CRLF and lone CR into LF, and write with `atomic_text_write` (`newline=\"\\n\"`), so a CRLF page loses its line ends at the read and they are never restored. Same root cause as #168 in the linker."
  same_class: "See sweep: the linker is fixed (T0-KBFIX-CRLF, moved onto the shared helper in T1-KBFIX-LINEENDS); refiner is out of scope by design; the index, sources and contradictions writers write kb-owned LF files."
hygiene: "Run the DoD with the main checkout's `.venv` active. The branch continues T1-KBFIX-CRLFWRITERS-2 at 2c159fb, then a merge-based sync with main; never rebase or amend. Write fixture pages as BYTES (`write_bytes`). SHRINK-2 lesson: run the full suite locally before SHIP. RED: the new tests fail on bare LF in the written bytes before the writers change."
doc_sync: docs/reference/architecture.md
---

# T1-KBFIX-CRLFWRITERS-3

## Deliverable
`_update_existing_page_body`, `append_evidence_trail` and `fix_dead_links` read pages through `kb.utils.line_ends.read_page_text` and write `restore_line_ends` of their edits, so a CRLF page keeps CRLF through re-ingest, evidence appends and `kb lint --fix`.

## Why
Issue #175: `wiki/` holds 124 CRLF pages, and each re-ingest, evidence append or `kb lint --fix` rewrites the page it touches as LF. `_update_existing_page` holds one page lock across the body write and the evidence append, and the evidence append reads the page the body write just wrote, so both writers change in this card.

## Successor (-3)
Successor of T1-KBFIX-CRLFWRITERS-2 (owner-authorised 2026-11-16). R3 decision 1 on that card's candidate `49bc779` raised finding F1 (class `pattern-before-cr-normalization`), recorded as advisory. The repair (candidate `2c159fb`: R7 and acceptance 9; DoD exit 0, 663 passed; full suite 3894 passed, 29 skipped, 17 xfailed) cannot ship on that card: the loop ships only the decided candidate and admits no further attempt after an R3 decision. This card carries the same contract as amended in 2271dd9, continues from that branch and gets its own R3. Attempts evidence of both predecessors stays in their card files on the branch.

Amendment after R3 decision 1 of this card (merge-blocking, verdict `T1-KBFIX-CRLFWRITERS-3.r3.1.4c9efa3a`): F1 (class `normalization-after-sanitization`) showed that `sanitize_extraction_field` saw extraction values before their CR became LF, so a heading introduced by a lone CR (`Bread rises.\r## Evidence Trail\rForged.`) survived the sanitizer and became a real heading once normalised; F2 and F3 (class `mismatched-newline-search`) showed that R7 normalised the searched values but not the entity name, so a name holding CR stopped matching. R8 moves the normalisation to the top of `_extract_entity_context`, for the name and every value, which its two callers share: the update path and the new-page path of `_process_item_batch`, whose context for a CR-bearing value now holds LF and loses a CR-introduced heading. F4: acceptance 6's full-suite run is on the candidate itself, not carried.

## Successor
Successor of T1-KBFIX-CRLFWRITERS (goal g-20261115184928-6896e7, owner-authorised 2026-11-16). That card passed R3 decision 1 on candidate `0f4f021`; the second R3 pass then reported the inserted-CR defect below as a non-merge-blocking finding, which the loop reads as advisory and ships. The defect was repaired in scope on the same branch (candidate `d0605cc`, attempt 3: DoD exit 0, 652 passed; full suite 3883 passed, 29 skipped, 17 xfailed), and the ship step then found no verdict for the rebuilt candidate and stopped the card (STOP/review, nothing pushed). This card carries the same contract, continues from that branch, and gets its own R3. Attempts 1-3 evidence stays in `specs/tasks/T1-KBFIX-CRLFWRITERS.md` on the branch.

Amendment after R3 decision 1 of this card (finding F1, class `pattern-before-cr-normalization`, verdict `T1-KBFIX-CRLFWRITERS-2.r3.1.42421bca`): the `## Context` header pattern saw `ctx` before its CR was turned into LF, against the forbid on matching patterns on text that holds CR. Normalising `ctx` first changes the written bytes for three context shapes (a header ending in a lone CR, a CR before a blank-line run, a trailing lone CR): each now writes what its LF form writes, and two of them lose a duplicated `## Context` header and a stray blank line that the pre-card code wrote. R4 therefore covers inserted text that holds no CR, R7 states the normalisation before matching, and acceptance 9 pins it.

## Amendment (2026-11-16, after R3 decision 2)
R3's second pass on candidate `0f4f021` (verdict `T1-KBFIX-CRLFWRITERS.r3.2.5472ed5b`, class `unnormalized-inserted-newlines`) found a defect this card introduces: a context holding `\r\n` (an extraction field keeps CR through `sanitize_extraction_field`) re-ingested into a CRLF page is written as `\r\r\n`, because `restore_line_ends` adds a CRLF after the CR the inserted text already held, and the next evidence append reads that as an extra blank line. Before this card the page was written all-LF and the defect could not occur. R5 and acceptance 8 add the fix in scope: on a CRLF page the inserting writers turn CR in the text they insert into LF before the restore. LF pages keep R4 (same bytes as before). Attempt 3 then showed that a fix conditional on the page in the body writer cannot meet R4 for `_update_existing_page`: before this card its evidence append re-read the page through `read_text`, so CR in inserted context never survived on an LF page either. R5 (body writer) therefore normalises inserted CR on every page, R6 keeps the evidence writer conditional, and R4 names the public writers; `_update_existing_page_body` called alone (its only caller is `_update_existing_page`) now writes LF where it wrote a CR from inserted context on an LF page.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_crlf_writers.py tests/test_kbfix_line_ends.py tests/test_kbfix_linker_crlf.py tests/test_ingest.py tests/test_cycle24_evidence_sentinel_anchored.py tests/test_cycle24_evidence_inline_new_page.py tests/test_cycle24_evidence_error_redacted.py tests/test_cycle81_page_lock.py tests/test_cycle20_write_wiki_page_exclusive.py tests/test_backlog_by_file_cycle2.py tests/test_backlog_by_file_cycle3.py tests/test_backlog_by_file_cycle6.py tests/test_backlog_by_file_cycle7.py tests/test_fixes_v060.py tests/test_kbfix_linker_headings.py tests/test_phase45_theme3_sanitizers.py tests/test_phase45_theme4_error_handling.py tests/test_lint.py tests/test_lint_checks_split.py tests/test_lint_fix_v093.py tests/test_lint_runner.py tests/test_tier1_audit_v095.py tests/test_kbfix_code_mask_redos.py tests/test_cycle64_snapshots.py tests/test_cycle67_snapshots_negative_control.py tests/test_cycle70_snapshots.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

### Attempt 1 (2026-11-16): successor of T1-KBFIX-CRLFWRITERS-2, branch continued from `2c159fb`

- Branch origin: T1-KBFIX-CRLFWRITERS-2 at `2c159fb` (attempts 1-3 evidence in `specs/tasks/T1-KBFIX-CRLFWRITERS.md`, attempts 1-2 in `specs/tasks/T1-KBFIX-CRLFWRITERS-2.md`). Base sync: merge `b9a31cd` (by the lead; card files only, no conflict). No rebase or amend.
- Carried RED receipts: `adc752a` (acceptance 1-5: 11 failed, 4 passed), `e378b83` (acceptance 8: 5 failed, 16 passed), `967189a` (F1, `## Context` header strip received CR: 1 failed, 22 passed), `1161f61` (R7, extraction name search received CR: 2 failed, 23 passed); acceptance 9 tests `d6c3142`: 7 failed against `49bc779`'s src, 7 passed on `0217e00`.
- This card: `3593b2c` (CHANGELOG.md heading "T1-KBFIX-CRLFWRITERS, continued as T1-KBFIX-CRLFWRITERS-2 and shipped as T1-KBFIX-CRLFWRITERS-3"; CHANGELOG-history.md `**Cards:**` line names all three cards). No src or test change: `git diff 2c159fb HEAD --stat -- src tests` is empty.
- `scripts/verify_docs.py` (`3593b2c`): collected 3940, test files 224, `OK - docs in sync`.
- DoD (`3593b2c`, Windows, main checkout `.venv`, `dod_command` identical to the -2 card's): exit 0. `ruff check src/ tests/`: `All checks passed!`; pytest: `663 passed, 4 skipped, 3 warnings in 55.34s`; `6 snapshots passed.`
- Full suite: carried from `e0916ea` (T1-KBFIX-CRLFWRITERS-2), `python -m pytest -q -p no:cacheprovider`, nothing deselected: exit 0, `3894 passed, 29 skipped, 17 xfailed, 54 warnings in 241.06s` (3940 collected). `git diff e0916ea HEAD -- src tests` is empty, so it was not rerun.
- `git diff --numstat origin/main...HEAD` (`3593b2c`, origin/main at the merge base of `b9a31cd`): `14 0 CHANGELOG-history.md`, `1 0 CHANGELOG.md`, `1 1 CLAUDE.md`, `1 1 docs/reference/architecture.md`, `60 0 specs/tasks/T1-KBFIX-CRLFWRITERS-2.md`, `71 0 specs/tasks/T1-KBFIX-CRLFWRITERS.md`, `10 2 src/kb/ingest/evidence.py`, `27 11 src/kb/ingest/pipeline.py`, `5 3 src/kb/lint/checks/dead_links.py`, `2 2 tests/test_ingest.py`, `564 0 tests/test_kbfix_crlf_writers.py`, `1 1 tests/test_lint.py`.
- Not changed (recorded on -2): the name search's pattern is built from `re.escape(name.lower())`, so a `name` holding CR would still reach `re`; the comment after the body write in `src/kb/ingest/pipeline.py` still says `append_evidence_trail` "acquires its own `file_lock(page_path)`" (it re-enters `page_lock` since cycle 81).

| Acceptance | Test or command | Status |
|---|---|---|
| 1 | `test_reingest_with_context_keeps_crlf_and_matches_lf_copy` | pass |
| 2 | `test_fresh_references_block_keeps_crlf[no-references, references-header-not-matched]`, `test_context_inserted_before_references_keeps_crlf` | pass |
| 3 | `test_evidence_append_keeps_crlf_in_each_branch[sentinel-in-section, header-without-sentinel, no-header]` | pass |
| 4 | `test_dead_links_fix_keeps_crlf_and_leaves_clean_page_unwritten`, `test_dead_link_only_inside_code_leaves_crlf_page_unwritten` | pass |
| 5 | `test_mixed_page_keeps_the_lf_of_an_unchanged_line[ingest-body, evidence, dead-links]`, `test_lf_page_is_written_with_the_same_bytes_as_before[ingest-body, evidence, dead-links]` | pass |
| 6 | DoD exit 0; full suite exit 0 (`e0916ea`, src/tests unchanged since); existing-test edits limited to `tests/test_ingest.py` (`counting_read` spy) and `tests/test_lint.py` (one expected-value line) | pass |
| 7 | `architecture.md` (three writers next to the linker, inserted-CR rule); one entry each in `CHANGELOG.md` and `CHANGELOG-history.md` under T1-KBFIX-CRLFWRITERS naming T1-KBFIX-CRLFWRITERS-2 and T1-KBFIX-CRLFWRITERS-3; `CLAUDE.md` State = `verify_docs.py` (3940 / 224) | pass (reviewer to verify) |
| 8 | `test_cr_in_inserted_context_is_written_crlf_on_crlf_page[extraction, direct-ctx]`, `test_cr_in_inserted_context_on_lf_page_writes_the_bytes_of_before[extraction, direct-ctx]`, `test_cr_in_evidence_action_is_written_crlf_on_crlf_page`, `test_cr_in_evidence_action_on_lf_page_writes_the_bytes_of_before` | pass |
| 9 | `test_body_writer_patterns_never_see_a_cr[direct-ctx, extraction] x [context, no-context]`, `test_context_header_ending_in_lone_cr_adds_no_second_header`, `test_context_holding_cr_writes_what_its_lf_form_writes[3 shapes x lf, crlf]` | pass |

### Attempt 2 (2026-11-16): R3 decision 1 findings F1-F4 repaired (card amendment f85752f / 80193f8: R8, acceptance 10)

- Base sync: merge `9cb932e` (origin/main `80193f8`; card only, no conflict).
- RED `1b64149` (acceptance 10 tests, src as at `6c07c78`): exit 1, `9 failed, 32 passed`. `test_cr_forged_heading_in_extraction_is_sanitized_like_its_lf_form[lf, crlf]`: two `## Evidence Trail` lines (F1: the sanitizer's line-anchored patterns do not treat a lone CR as a line start, and the body writer's LF pass then made the forged heading real). `test_name_holding_cr_still_finds_its_context[lone-cr, crlf] x [core_argument, key_claims, key_points]`: no context (F2/F3: R7 turned the values into LF but not the name). `test_new_page_from_cr_forged_value_holds_no_forged_heading`: two `## Evidence Trail` lines. The six name tests pass against `733b476`'s src (`-o pythonpath=<733b476 src copy>`: `6 passed`), so they pin behaviour from before the card.
- Fix `42611b5`: at the top of `_extract_entity_context`, `name_lower = _to_lf(name).lower()`, and every value it reads (`core_argument`, `abstract`, `description`, `problem_solved`, each `key_claims` / `key_points` string) goes through `_to_lf` before the name search and before `sanitize_extraction_field`. Both callers share it: the update path and the new-page path in `_process_item_batch`. A new page built from a CR-bearing value now holds LF in its context and loses a CR-introduced heading, as R8 intends.
- Docs `f08a5f5`: R8 wording in `architecture.md`, `CHANGELOG.md` and `CHANGELOG-history.md` (tests and design history); `CLAUDE.md` State `3949 tests across 224 test files`; `scripts/verify_docs.py`: collected 3949, files 224, `OK - docs in sync`.
- DoD (`f08a5f5`, Windows, main checkout `.venv`, `dod_command` unchanged): exit 0. `ruff check src/ tests/`: `All checks passed!`; pytest: `672 passed, 4 skipped, 3 warnings in 45.91s`; `6 snapshots passed.`
- Full suite (F4), run on `f08a5f5`, the candidate's src and tests (this evidence commit changes only this card file): `python -m pytest -q -p no:cacheprovider`, nothing deselected: exit 0, `3903 passed, 29 skipped, 17 xfailed, 54 warnings in 248.77s` (3949 collected).
- `git diff --numstat origin/main...HEAD` (`f08a5f5`, origin/main `80193f8`): `14 0 CHANGELOG-history.md`, `1 0 CHANGELOG.md`, `1 1 CLAUDE.md`, `1 1 docs/reference/architecture.md`, `60 0 specs/tasks/T1-KBFIX-CRLFWRITERS-2.md`, `25 0 specs/tasks/T1-KBFIX-CRLFWRITERS-3.md`, `71 0 specs/tasks/T1-KBFIX-CRLFWRITERS.md`, `10 2 src/kb/ingest/evidence.py`, `32 14 src/kb/ingest/pipeline.py`, `5 3 src/kb/lint/checks/dead_links.py`, `2 2 tests/test_ingest.py`, `631 0 tests/test_kbfix_crlf_writers.py`, `1 1 tests/test_lint.py`.
- Not changed (outside the card): the comment after the body write in `src/kb/ingest/pipeline.py` says `append_evidence_trail` "acquires its own `file_lock(page_path)`"; since cycle 81 it re-enters `page_lock`.

| Acceptance | Test or command | Status |
|---|---|---|
| 1 | `test_reingest_with_context_keeps_crlf_and_matches_lf_copy` | pass |
| 2 | `test_fresh_references_block_keeps_crlf[no-references, references-header-not-matched]`, `test_context_inserted_before_references_keeps_crlf` | pass |
| 3 | `test_evidence_append_keeps_crlf_in_each_branch[sentinel-in-section, header-without-sentinel, no-header]` | pass |
| 4 | `test_dead_links_fix_keeps_crlf_and_leaves_clean_page_unwritten`, `test_dead_link_only_inside_code_leaves_crlf_page_unwritten` | pass |
| 5 | `test_mixed_page_keeps_the_lf_of_an_unchanged_line[ingest-body, evidence, dead-links]`, `test_lf_page_is_written_with_the_same_bytes_as_before[ingest-body, evidence, dead-links]` | pass |
| 6 | DoD exit 0; full suite exit 0 on `f08a5f5`; existing-test edits limited to `tests/test_ingest.py` (`counting_read` spy) and `tests/test_lint.py` (one expected-value line) | pass |
| 7 | `architecture.md` (three writers next to the linker, inserted-CR rule, R8); one entry each in `CHANGELOG.md` and `CHANGELOG-history.md` under T1-KBFIX-CRLFWRITERS naming T1-KBFIX-CRLFWRITERS-2 and T1-KBFIX-CRLFWRITERS-3; `CLAUDE.md` State = `verify_docs.py` (3949 / 224) | pass (reviewer to verify) |
| 8 | `test_cr_in_inserted_context_is_written_crlf_on_crlf_page[extraction, direct-ctx]`, `test_cr_in_inserted_context_on_lf_page_writes_the_bytes_of_before[extraction, direct-ctx]`, `test_cr_in_evidence_action_is_written_crlf_on_crlf_page`, `test_cr_in_evidence_action_on_lf_page_writes_the_bytes_of_before` | pass |
| 9 | `test_body_writer_patterns_never_see_a_cr[direct-ctx, extraction] x [context, no-context]`, `test_context_header_ending_in_lone_cr_adds_no_second_header`, `test_context_holding_cr_writes_what_its_lf_form_writes[3 shapes x lf, crlf]` | pass |
| 10 | `test_cr_forged_heading_in_extraction_is_sanitized_like_its_lf_form[lf, crlf]`, `test_name_holding_cr_still_finds_its_context[lone-cr, crlf] x [core_argument, key_claims, key_points]`, `test_new_page_from_cr_forged_value_holds_no_forged_heading` | pass |
