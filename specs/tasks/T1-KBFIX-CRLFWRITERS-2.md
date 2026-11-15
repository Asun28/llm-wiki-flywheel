---
id: T1-KBFIX-CRLFWRITERS-2
title: "Re-ingest, evidence appends and `kb lint --fix` write a CRLF page back with its own line ends (#175, part 2)"
status: todo
branch: T1-KBFIX-CRLFWRITERS-2
worktree: D:\wt\llm-wiki-flywheel\T1-KBFIX-CRLFWRITERS-2
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
acceptance:
  - 1. `test_kbfix_crlf_writers.py`: `_update_existing_page` on an all-CRLF page with `## Context` and `## References` sections, re-ingesting a new source with a context, writes a page in which every LF is preceded by CR, holding the new frontmatter `source:` entry, the new reference line, the new `### From` subsection and the new evidence entry; the page with CRLF turned to LF equals what the same call writes on the LF copy of the page. [R1] [R2] [dod arm 2]
  - 2. Same file: on an all-CRLF page, the branch that appends a fresh `## References` block and the branch that inserts a `## Context` section before `## References` each leave every line end CRLF. [R1] [dod arm 2]
  - 3. Same file: `append_evidence_trail` alone on an all-CRLF page, in each of its three branches (sentinel in the section, header without sentinel, no header), leaves every line end CRLF and inserts the entry where it does on the LF copy. [R2] [dod arm 2]
  - 4. Same file: `fix_dead_links` on an all-CRLF page with two broken links 20 lines apart replaces both and leaves every line end CRLF; a CRLF page with no broken link is not written (bytes and mtime unchanged). [R3] [dod arm 2]
  - 5. Same file: on a mixed page (CRLF on most lines, LF on one unchanged line) each writer keeps that line's LF; on an all-LF page each writer's output equals the expected bytes written out in the test. [R1] [R2] [R3] [R4] [dod arm 2]
  - 6. Every test file in the DoD passes. The only edits to existing tests are two: `tests/test_ingest.py` (`counting_read`, about line 1457), where the read-count spy moves from `Path.read_text` to `Path.read_bytes` because the page is now read as bytes and its `read_count[0] == 1` assertion is unchanged; and `tests/test_lint.py::test_atomic_text_write_patch_reaches_dead_link_fix_submodule` (about line 675), whose expected write content is computed from `page.read_bytes().decode("utf-8")` instead of `page.read_text(encoding="utf-8")`, because its fixture is written with `write_text` (CRLF on Windows) and the `read_text` expectation pinned the LF rewrite this card removes; the shared fixture `_write_pkg_const_fold_page` and every other assertion stay unchanged. The full suite passes locally on the candidate before SHIP (receipt in Attempt evidence). [R1] [dod arm 2]
  - 7. `docs/reference/architecture.md` names the three writers next to the linker as users of `kb.utils.line_ends`; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry for this fix (under T1-KBFIX-CRLFWRITERS, the card this one continues, naming this card too); the counts in the `State` line of `CLAUDE.md` equal the collected test count and test-file count on the candidate (reviewer-verified).
  - 8. `test_kbfix_crlf_writers.py`: `_update_existing_page` on an all-CRLF page, once with an extraction whose `core_argument` is `"Bread rises.\r\nBake it."` and once with a directly supplied `ctx` holding a CRLF and a lone CR, writes a page with no `"\r\r"` in its bytes and every line end CRLF, and after its evidence append has as many lines as the LF copy's output; `append_evidence_trail` with an `action` holding a CRLF on an all-CRLF page writes no `"\r\r"`; on an all-LF page the same calls write the bytes they wrote before this change (written out literally in the test). [R4] [R5] [R6] [dod arm 2]
  - 9. `test_kbfix_crlf_writers.py`: while `_update_existing_page` re-ingests a `ctx` holding a CRLF and a lone CR into a CRLF page with a `## Context` section, no `re` call made through `kb.ingest.pipeline` receives a string holding CR; a `ctx` of `"## ContextRises."` re-ingested into an LF page that has `## Context` adds no second `## Context` header, and each of the three context shapes of the attempt-2 differential writes the bytes its LF form writes. [R4] [R7] [dod arm 2]
depends_on: [T1-KBFIX-LINEENDS]
budget: 250
sweep: "Twelve paths: three src writers, one new and two existing test files, four doc files, this card and its predecessor's card (which holds attempts 1-3 evidence on the branch this card continues). `atomic_text_write` callers in src/kb (grep `atomic_text_write(`): page writers that read the page first are `ingest/pipeline.py:995` (R1), `ingest/evidence.py:250` (R2), `lint/checks/dead_links.py:115` (R3), the linker (moved in T1-KBFIX-LINEENDS) and `review/refiner.py:323` (CRLF to LF on purpose). Not page bodies: `ingest/pipeline.py:309` (contradictions), `:1044`/`:1055` (`_sources.md`), `:1109` (`index.md`), publish, augment, query formats, `utils/pages.py:256` (`frontmatter.dumps` of a Post). Existing tests that spy on `Path.read_text`: `tests/test_ingest.py:1457` changes (acceptance 6); `tests/test_cycle35_ingest_index_writers.py` spies on the `_sources.md` / `index.md` writers, which do not change; the others spy on verdicts, compiler, refiner and context readers. Missed by that grep and found by attempt 1 on Windows: `tests/test_lint.py:675` expects `fix_dead_links` to write `read_text` output of a `write_text` fixture (acceptance 6)."
forbid: [weakening an existing test, matching any pattern on text that still holds CR, releasing the page lock between the body write and the evidence append, a model call or network request in tests]
non_goals: [`refine_page` (CRLF to LF on purpose), `_update_sources_mapping` / `_update_index_batch` / the contradictions writer (kb-written LF files; 0 CRs in `wiki/index.md` and `wiki/_sources.md`), `save_page_frontmatter` (reserializes the Post), lone CR kept as CR (written as LF)]
diagnosis:
  root_cause: "The three writers read with `Path.read_text(encoding=\"utf-8\")`, whose universal-newline mode turns CRLF and lone CR into LF, and write with `atomic_text_write` (`newline=\"\\n\"`), so a CRLF page loses its line ends at the read and they are never restored. Same root cause as #168 in the linker."
  same_class: "See sweep: the linker is fixed (T0-KBFIX-CRLF, moved onto the shared helper in T1-KBFIX-LINEENDS); refiner is out of scope by design; the index, sources and contradictions writers write kb-owned LF files."
hygiene: "Run the DoD with the main checkout's `.venv` active. The branch continues T1-KBFIX-CRLFWRITERS at d0605cc, then a merge-based sync with main; never rebase or amend. Write fixture pages as BYTES (`write_bytes`). SHRINK-2 lesson: run the full suite locally before SHIP. RED: the new tests fail on bare LF in the written bytes before the writers change."
doc_sync: docs/reference/architecture.md
---

# T1-KBFIX-CRLFWRITERS-2

## Deliverable
`_update_existing_page_body`, `append_evidence_trail` and `fix_dead_links` read pages through `kb.utils.line_ends.read_page_text` and write `restore_line_ends` of their edits, so a CRLF page keeps CRLF through re-ingest, evidence appends and `kb lint --fix`.

## Why
Issue #175: `wiki/` holds 124 CRLF pages, and each re-ingest, evidence append or `kb lint --fix` rewrites the page it touches as LF. `_update_existing_page` holds one page lock across the body write and the evidence append, and the evidence append reads the page the body write just wrote, so both writers change in this card.

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

### Attempt 1 (2026-11-16): successor of T1-KBFIX-CRLFWRITERS, branch continued from `d0605cc`

- Base sync: merge `f3a0f65` (origin/main `8b37f03`, which adds T1-KBEVAL-ALTFIG, PR #177, and this card). Conflicts in `CHANGELOG.md` and `CHANGELOG-history.md` resolved keeping both entries, T1-KBFIX-CRLFWRITERS above T1-KBEVAL-ALTFIG. Main changed no file under `src/` or `tests/`, so no behaviour change came with the merge. No rebase or amend.
- Commits carried from the predecessor (attempts 1-3 evidence in `specs/tasks/T1-KBFIX-CRLFWRITERS.md`): RED `adc752a` (acceptance 1-5: 11 failed, 4 passed) and `e378b83` (acceptance 8: 5 failed, 16 passed); fixes `f157ebb` (three writers on `read_page_text` / `restore_line_ends`), `d46bc32` (R6 guard in both writers) and `37cecd3` (R5: body writer on every page); test edits `07e2352` (`tests/test_lint.py`) and `f157ebb` (`tests/test_ingest.py` spy); docs `a7474e4`, `23db60b`.
- This card: `bb86bdc` (CHANGELOG.md entry heading and CHANGELOG-history.md `**Cards:**` line name T1-KBFIX-CRLFWRITERS-2). No src or test change.
- `scripts/verify_docs.py` (`bb86bdc`): collected 3929, test files 224, `OK - docs in sync`; `CLAUDE.md` State: `3929 tests across 224 test files`.
- DoD (`bb86bdc`, Windows, main checkout `.venv`, command read from this card's `dod_command`, same text as the predecessor's): exit 0. `ruff check src/ tests/`: `All checks passed!`; pytest: `652 passed, 4 skipped, 3 warnings in 86.78s`; `6 snapshots passed.`
- Full suite (`bb86bdc`, `python -m pytest -q -p no:cacheprovider`, nothing deselected): exit 0, `3883 passed, 29 skipped, 17 xfailed, 54 warnings in 339.14s` (3929 collected).
- `git diff --numstat origin/main...HEAD` (`bb86bdc`, origin/main `8b37f03`): `14 0 CHANGELOG-history.md`, `1 0 CHANGELOG.md`, `1 1 CLAUDE.md`, `1 1 docs/reference/architecture.md`, `71 0 specs/tasks/T1-KBFIX-CRLFWRITERS.md`, `10 2 src/kb/ingest/evidence.py`, `12 7 src/kb/ingest/pipeline.py`, `5 3 src/kb/lint/checks/dead_links.py`, `2 2 tests/test_ingest.py`, `479 0 tests/test_kbfix_crlf_writers.py`, `1 1 tests/test_lint.py`.
- Follow-up note (outside this card): the comment after the body write in `src/kb/ingest/pipeline.py` says `append_evidence_trail` "acquires its own `file_lock(page_path)`"; since cycle 81 it re-enters `page_lock`.

| Acceptance | Test or command | Status |
|---|---|---|
| 1 | `test_reingest_with_context_keeps_crlf_and_matches_lf_copy` | pass |
| 2 | `test_fresh_references_block_keeps_crlf[no-references, references-header-not-matched]`, `test_context_inserted_before_references_keeps_crlf` | pass |
| 3 | `test_evidence_append_keeps_crlf_in_each_branch[sentinel-in-section, header-without-sentinel, no-header]` | pass |
| 4 | `test_dead_links_fix_keeps_crlf_and_leaves_clean_page_unwritten`, `test_dead_link_only_inside_code_leaves_crlf_page_unwritten` | pass |
| 5 | `test_mixed_page_keeps_the_lf_of_an_unchanged_line[ingest-body, evidence, dead-links]`, `test_lf_page_is_written_with_the_same_bytes_as_before[ingest-body, evidence, dead-links]` | pass |
| 6 | DoD exit 0; full suite exit 0; existing-test edits limited to `tests/test_ingest.py` (`counting_read` spy) and `tests/test_lint.py` (one expected-value line) | pass |
| 7 | `architecture.md` (three writers next to the linker, inserted-CR rule); one entry each in `CHANGELOG.md` and `CHANGELOG-history.md` under T1-KBFIX-CRLFWRITERS naming T1-KBFIX-CRLFWRITERS-2; `CLAUDE.md` State = `verify_docs.py` (3929 / 224) | pass (reviewer to verify) |
| 8 | `test_cr_in_inserted_context_is_written_crlf_on_crlf_page[extraction, direct-ctx]`, `test_cr_in_inserted_context_on_lf_page_writes_the_bytes_of_before[extraction, direct-ctx]`, `test_cr_in_evidence_action_is_written_crlf_on_crlf_page`, `test_cr_in_evidence_action_on_lf_page_writes_the_bytes_of_before` | pass |

### Attempt 2 (2026-11-16): R3 decision 1 finding F1 repaired; BLOCKED on a byte change the repair cannot avoid

- RED `967189a` (`test_body_writer_patterns_never_see_a_cr[context-section, no-context-section]`; it replaces `kb.ingest.pipeline.re` with a recorder that delegates to `re`): src identical to `49bc779`, exit 1, `1 failed, 22 passed`. `[context-section]` fails: the `## Context` header strip receives `'## Context\r\n\r\nBread rises.\r\nBake it.\rCool it.'`. `[no-context-section]` passes, because no pattern sees `ctx` on that branch.
- Fix `fc1c3db`: new `_to_lf`; `ctx` goes through `_to_lf` right after `_extract_entity_context` or the direct argument; `ref_line` is built through `_to_lf` (`source_ref` can hold a CR on POSIX, because `make_source_ref` does not filter filenames, and `verb` is a caller argument); `_inline_code` gets `_to_lf(source_ref)`; `safe_ref` is unchanged (`yaml_escape` escapes CR); the whole-content `_to_lf` before the restore stays as a guard.
- DoD (`fc1c3db`): exit 0. `ruff check src/ tests/`: `All checks passed!`; pytest: `654 passed, 4 skipped, 3 warnings`; `6 snapshots passed.` Full suite not run (blocked).
- `append_evidence_trail`: F1 does not apply. Its patterns (`_mask_fenced_blocks`, `_EVIDENCE_TRAIL_HEADER_RE`, `_NEXT_H2_RE`) and the `SENTINEL in span` check run on the page text before the entry is concatenated, and nothing matches the entry afterwards.
- Remaining instance (not changed): `_extract_entity_context` runs `re.search(rf"\b{name}\b", val.lower())` on extraction fields that can hold CR, before `ctx` exists. The result does not depend on CR unless `name` holds a line end. A fix that leaves output unchanged searches `_to_lf(val.lower())` and keeps appending the raw `val`. That function is shared with new-page writes and is outside the card's three writers.
- Blocker: the repair changes written bytes. A differential over 192 body-writer inputs (4 bodies x 8 contexts x 3 `source_ref` x LF/CRLF page), `49bc779` src against `fc1c3db` src, differs in 36 cases, all from 3 context shapes. On LF pages `_update_existing_page` on `733b476` (pre-card) equals `49bc779` in 8 of 8 probed cases and differs from `fc1c3db` in 3:
  - `"## Context\rRises."` with an existing `## Context`: pre-card and `49bc779` do not strip the header (`\s*` takes the CR, `\n+` then fails), so a second `## Context` lands inside the section; `fc1c3db` strips it.
  - `"## Context  \r\nRises.\r\n\r\n"` with an existing `## Context`: `rstrip("\n")` stops at the CR, so pre-card and `49bc779` keep a blank line before `## References`; `fc1c3db` does not.
  - `"Rises.\r"` with no `## Context`: `f"{ctx}\n\n"` joins the CR and the LF into one line end in pre-card and `49bc779`; `fc1c3db` writes one more blank line.
  In each case `fc1c3db` writes what the same context with LF ends writes. Any fix of F1 changes the first case, because there the old output depends on the header pattern seeing the CR. R4 (pre-card bytes on LF pages) and the forbid (no pattern on text that holds CR) conflict for a context holding a CR next to a line end.

#### Attempt 2, resumed after ruling `2271dd9` (option A: keep `fc1c3db`; R4 qualified, R7 and acceptance 9 added)

- Base sync: merge `9efb92a` (origin/main `2271dd9`; card only, no conflict).
- R7, extraction search: RED `1161f61` (the recorder test now runs `_update_existing_page` with a direct context and with an extraction whose `core_argument` and `key_claims` hold CR, on CRLF pages with and without `## Context`): exit 1, `2 failed, 23 passed`; `[extraction-context]` and `[extraction-no-context]` fail because `_extract_entity_context`'s name search receives the values with their CRs. Fix `0217e00`: the search runs on `_to_lf(val.lower())` / `_to_lf(claim.lower())`, and the appended value is unchanged, so new-page output (the other caller, `pipeline.py` new-page path) is the same.
- Acceptance 9 tests `d6c3142`: `test_context_header_ending_in_lone_cr_adds_no_second_header` and `test_context_holding_cr_writes_what_its_lf_form_writes[header-lone-cr, trailing-crlf-blank, trailing-lone-cr] x [lf, crlf]`. Against `49bc779`'s src (`-o pythonpath=<49bc779 src copy>`): `7 failed`; on `0217e00`: `7 passed`.
- Docs `e0916ea`: R7 wording in `architecture.md`, `CHANGELOG.md`, `CHANGELOG-history.md` (with the F1 design history); `CLAUDE.md` State `3940 tests across 224 test files`; `scripts/verify_docs.py`: collected 3940, files 224, `OK - docs in sync`.
- DoD (`e0916ea`, Windows, main checkout `.venv`, `dod_command` unchanged since `49bc779`): exit 0. `ruff check src/ tests/`: `All checks passed!`; pytest: `663 passed, 4 skipped, 3 warnings in 52.47s`; `6 snapshots passed.`
- Full suite (`e0916ea`, `python -m pytest -q -p no:cacheprovider`, nothing deselected): exit 0, `3894 passed, 29 skipped, 17 xfailed, 54 warnings in 241.06s` (3940 collected).
- `git diff --numstat origin/main...HEAD` (`e0916ea`, origin/main `2271dd9`): `14 0 CHANGELOG-history.md`, `1 0 CHANGELOG.md`, `1 1 CLAUDE.md`, `1 1 docs/reference/architecture.md`, `37 0 specs/tasks/T1-KBFIX-CRLFWRITERS-2.md`, `71 0 specs/tasks/T1-KBFIX-CRLFWRITERS.md`, `10 2 src/kb/ingest/evidence.py`, `27 11 src/kb/ingest/pipeline.py`, `5 3 src/kb/lint/checks/dead_links.py`, `2 2 tests/test_ingest.py`, `564 0 tests/test_kbfix_crlf_writers.py`, `1 1 tests/test_lint.py`.
- Not changed: the pattern string of the name search includes `re.escape(name.lower())`; a `name` holding CR would still reach `re`. Entity names come from extraction and none of the probed inputs holds CR; normalising `name` would change which pages match for such a name.

| Acceptance | Test or command | Status |
|---|---|---|
| 1 | `test_reingest_with_context_keeps_crlf_and_matches_lf_copy` | pass |
| 2 | `test_fresh_references_block_keeps_crlf[no-references, references-header-not-matched]`, `test_context_inserted_before_references_keeps_crlf` | pass |
| 3 | `test_evidence_append_keeps_crlf_in_each_branch[sentinel-in-section, header-without-sentinel, no-header]` | pass |
| 4 | `test_dead_links_fix_keeps_crlf_and_leaves_clean_page_unwritten`, `test_dead_link_only_inside_code_leaves_crlf_page_unwritten` | pass |
| 5 | `test_mixed_page_keeps_the_lf_of_an_unchanged_line[ingest-body, evidence, dead-links]`, `test_lf_page_is_written_with_the_same_bytes_as_before[ingest-body, evidence, dead-links]` | pass |
| 6 | DoD exit 0; full suite exit 0; existing-test edits limited to `tests/test_ingest.py` (`counting_read` spy) and `tests/test_lint.py` (one expected-value line) | pass |
| 7 | `architecture.md` (three writers next to the linker, inserted-CR rule); one entry each in `CHANGELOG.md` and `CHANGELOG-history.md` under T1-KBFIX-CRLFWRITERS naming T1-KBFIX-CRLFWRITERS-2; `CLAUDE.md` State = `verify_docs.py` (3940 / 224) | pass (reviewer to verify) |
| 8 | `test_cr_in_inserted_context_is_written_crlf_on_crlf_page[extraction, direct-ctx]`, `test_cr_in_inserted_context_on_lf_page_writes_the_bytes_of_before[extraction, direct-ctx]`, `test_cr_in_evidence_action_is_written_crlf_on_crlf_page`, `test_cr_in_evidence_action_on_lf_page_writes_the_bytes_of_before` | pass |
| 9 | `test_body_writer_patterns_never_see_a_cr[direct-ctx, extraction] x [context, no-context]`, `test_context_header_ending_in_lone_cr_adds_no_second_header`, `test_context_holding_cr_writes_what_its_lf_form_writes[3 shapes x lf, crlf]` | pass |
