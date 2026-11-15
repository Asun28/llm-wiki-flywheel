---
id: T1-KBFIX-LINEENDS
title: "`kb.utils.line_ends` restores a page's line ends after any number of edits, added lines taking the page's most-used end, and the linker uses it (#175, part 1)"
status: todo
branch: T1-KBFIX-LINEENDS
worktree: D:\wt\llm-wiki-flywheel\T1-KBFIX-LINEENDS
plan_ref: plans/kb-fixes-2.md#order-of-work
allow_paths:
  - src/kb/utils/line_ends.py
  - src/kb/compile/linker.py
  - tests/test_kbfix_line_ends.py
  - docs/reference/architecture.md
  - docs/reference/module-map.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T1-KBFIX-LINEENDS.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_line_ends.py tests/test_kbfix_linker_crlf.py tests/test_kbfix_linker_headings.py tests/test_kbfix_code_mask_redos.py tests/test_cycle18_linker_lock.py tests/test_cycle19_inject_batch_e2e.py tests/test_cycle19_inject_wikilinks_batch.py tests/test_cycle81_page_lock.py tests/test_compile.py -q
dod_exit: 0
freeze: true
requirements:
  - R1. The function `kb.utils.line_ends.read_page_text(path)` shall return, from one read of the file's bytes, the text with every CRLF and lone CR turned into LF (equal to `Path.read_text(encoding="utf-8")`) and the file's line ends in order, `"\r\n"` for a CRLF and `"\n"` for an LF or a lone CR.
  - R2. IF `ends` holds no CRLF, THEN the function `kb.utils.line_ends.restore_line_ends(text, original, ends)` shall return `text` unchanged.
  - R3. WHEN `ends` holds a CRLF, the function `restore_line_ends` shall match the common leading and trailing lines of `original` and `text` first and run a line diff (`difflib.SequenceMatcher`, `autojunk=False`, over the LF-split lines) on the lines between them, giving each line aligned with an equal line of `original` that line's own end and the lines of one replaced run, paired from the end of the run, the replaced lines' ends.
  - R4. WHEN `ends` holds a CRLF, the function `restore_line_ends` shall give every other line of `text` that has a line end (an added line, or an original last line that had no end) the most-used end of `ends`, and LF on a tie.
  - R5. The linker (`inject_wikilinks`, `inject_wikilinks_batch`) shall read pages through `read_page_text` and write `restore_line_ends` of its result, with no copy of either (`_read_page`, `_restore_line_ends`, `_LINE_END_RE`) left in `kb.compile.linker`.
acceptance:
  - 1. `test_kbfix_line_ends.py`: a file holding CRLF, LF and lone CR line ends gives the text `Path.read_text(encoding="utf-8")` gives and the ends `["\r\n", "\n", "\n"]`; a file with no line end gives `[]`. [R1] [dod arm 2]
  - 2. Same file: on an all-LF `original`, an edit that adds, removes and replaces lines returns `text` unchanged (`is` the same object or equal). [R2] [dod arm 2]
  - 3. Same file: an all-CRLF page of 10 lines edited on line 2 and line 9 keeps CRLF on lines 3-8; on a mixed page a replaced LF line keeps LF and a replaced CRLF line keeps CRLF; a line merged from two lines keeps the second line's end; a line split in two gives the first part the most-used end and the second part the original end; and an edited line whose old text also appears later on the page keeps its own end (`original` = `"matters\n\n\n\nx Hydration\n x \nmatters\nmatters"`, ends `["\n", "\n", "\n", "\n", "\r\n", "\n", "\r\n"]`, the seventh line edited: it keeps CRLF). [R3] [dod arm 2]
  - 4. Same file: an added line gets CRLF on an all-CRLF page, CRLF on a page with 3 CRLF and 1 LF, LF on a page with 1 CRLF and 3 LF, and LF on a 2/2 tie; an original last line with no end that gains one gets the most-used end, and a `text` with no final line end gets none. [R4] [dod arm 2]
  - 5. Same file, a seeded property test of at least 2,000 random multi-edit cases (pages of random CRLF/LF mixes, 1-5 edits each adding, removing or replacing lines): the result with CRLF turned to LF equals `text`, an all-CRLF page stays all-CRLF, an all-LF page returns `text`; with a copy of the PR 174 one-splice restore kept in the test file as the oracle, at least 2,000 seeded single splices on mixed pages whose inserted text holds no LF give the oracle's bytes; and a 5,000-line CRLF page with 50 scattered edits restores in under 5 seconds on the DoD runner. [R2] [R3] [R4] [dod arm 2]
  - 6. All 27 tests of `tests/test_kbfix_linker_crlf.py` and every other test file in the DoD pass with no existing test edited; `src/kb/compile/linker.py` holds none of `_read_page`, `_restore_line_ends`, `_LINE_END_RE` and imports `read_page_text` and `restore_line_ends` from `kb.utils.line_ends`. [R5] [dod arm 2]
  - 7. `docs/reference/architecture.md` describes the shared helper and the added-line rule where it describes the linker's CRLF handling; `docs/reference/module-map.md` lists `kb.utils.line_ends`; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal the collected test count and test-file count on the candidate (reviewer-verified).
depends_on: []
budget: 250
sweep: "Nine paths: one new src module, the linker, one new test file, five doc files and this card. Callers of `_read_page` / `_restore_line_ends`: `src/kb/compile/linker.py` only (lines 303, 325, 378, 496, 581, 634); no test imports either (`tests/test_kbfix_linker_crlf.py` imports only `inject_wikilinks`, `inject_wikilinks_batch`). The three other writers (#175 part 2) are card T1-KBFIX-CRLFWRITERS."
forbid: [an edit to an existing test, a `kb` import inside `kb.utils.line_ends`, matching any pattern on text that still holds CR, a model call or network request in tests]
non_goals: [the ingest, evidence and dead-links writers (T1-KBFIX-CRLFWRITERS), `refine_page` (CRLF to LF on purpose), lone CR kept as CR (written as LF, as today)]
diagnosis:
  root_cause: "#174 restored line ends with a one-splice diff (common prefix and suffix), which is right for the linker's single link insertion but turns every line between the first and last edit into LF for a writer that edits in several places, and gives an LF inside inserted text LF on a CRLF page."
  same_class: "The three other page writers of #175 need the multi-edit restore; they move onto this helper in T1-KBFIX-CRLFWRITERS."
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixture pages as BYTES (`write_bytes`): `write_text` on Windows turns `\\n` into `\\r\\n` and hides the defect. RED: the new test file fails on import (`kb.utils.line_ends` missing) and then on behaviour; record both in Attempt evidence."
doc_sync: docs/reference/architecture.md
---

# T1-KBFIX-LINEENDS

## Deliverable
A leaf module `kb.utils.line_ends` with `read_page_text` and a line-level `restore_line_ends` that keeps every unchanged and replaced line's end and gives added lines the page's most-used end. The linker moves onto it with no change to any of its pinned outputs.

## Why
Issue #175: three page writers turn CRLF pages into LF. #174's one-splice restore cannot serve them because they make several separate edits and add lines. Owner decisions 2026-11-16 (intent/kb-fixes-2.md): added lines take the page's most-used end (LF on a tie); one shared helper for all four writers, the linker included.

## Amendment (2026-11-16, before R3)
Attempt 1 (candidate `cd11126`) implemented revision 0 and found its rule defective: a plain line diff aligns an edited line's unchanged twin further down the page as the equal line, so the edited line is treated as added and takes the most-used end instead of its own (2 of 8,147 one-splice cases on mixed pages in a differential against #174). Pairing a replaced run from its start also gave a joined line the first line's end, while the end that survives a join is the second line's. R3 now matches the common leading and trailing lines before the diff and pairs a replaced run from its end; acceptance 3 and 5 pin both, the latter with #174's restore as the oracle for splices that insert no LF. All-CRLF and all-LF pages were not affected.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_line_ends.py tests/test_kbfix_linker_crlf.py tests/test_kbfix_linker_headings.py tests/test_kbfix_code_mask_redos.py tests/test_cycle18_linker_lock.py tests/test_cycle19_inject_batch_e2e.py tests/test_cycle19_inject_wikilinks_batch.py tests/test_cycle81_page_lock.py tests/test_compile.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1 (implementer, 2026-11-16). Worktree `D:\wt\llm-wiki-flywheel\T1-KBFIX-LINEENDS`, branch `T1-KBFIX-LINEENDS`.

- Base: origin/main 9fffe1c; `git fetch origin main` before this entry: origin/main still 9fffe1c, branch is 9fffe1c + 6 commits, no merge needed.
- Commits: d02fec9 RED tests; 8d2dc24 RED stub; ae75056 RED timing test reports the first differing offset (a plain `==` on the 5,000-line result made pytest diff two 250 KB strings past the 120 s suite timeout); 74ad7ef GREEN module + linker; 5f65fc4 docs; this entry.
- Interpreter: main checkout `.venv` (`D:\Projects\llm-wiki-flywheel\.venv\Scripts\python.exe`, `ruff.exe`); pytest `pythonpath = ["src"]` imports the worktree: `kb.utils.line_ends` resolves to `D:\wt\llm-wiki-flywheel\T1-KBFIX-LINEENDS\src\kb\utils\line_ends.py` (the module does not exist in the main checkout).

### RED receipt
- Import RED at d02fec9: `python -m pytest tests/test_kbfix_line_ends.py -q -p no:cacheprovider` exit 2: `E   ModuleNotFoundError: No module named 'kb.utils.line_ends'`, `1 error in 0.63s`.
- Behavioural RED at 8d2dc24 (stub returning `("", [])` and `""`): same command exit 1, `16 failed in 3.24s`, every failure an `AssertionError` (e.g. `test_kbfix_line_ends.py:58: AssertionError: assert '' == 'line 1\r\nli...\nline 10\r\n'`).
- Against the #174 one-splice restore (probe, not committed): 8 of 16 fail: `test_two_separate_edits_keep_crlf_on_every_line_between_them`, both `test_a_merged_line_keeps_the_first_replaced_lines_end` cases, `test_an_added_line_gets_the_most_used_end[all-crlf]` and `[3-crlf-1-lf]`, `test_an_original_last_line_that_gains_an_end_gets_the_most_used_end[most-used-crlf]`, the property test and the timing test (`first difference at offset 5503`).

### DoD receipt
- Command (exact `dod_command`, worktree root, `.venv\Scripts` first on PATH) at 5f65fc4: exit 0. `ruff check src/ tests/`: `All checks passed!`; pytest: `209 passed in 15.36s`. Output sha256 prefix 68e6a8fcd89e4096.
- Full suite at 74ad7ef (`python -m pytest -q -p no:cacheprovider`): exit 0, `3858 passed, 29 skipped, 17 xfailed, 54 warnings in 268.00s` (3904 collected). The docs commit changes no code or test.
- `python scripts/verify_docs.py` at the docs tree: `pytest collected tests = 3904`, `test file count = 223`, `OK - docs in sync.`

### Acceptance map
| Item | Proof |
|---|---|
| 1 [R1] | `test_read_page_text_gives_read_text_and_the_line_ends`, `test_read_page_text_without_a_line_end_gives_no_ends` |
| 2 [R2] | `test_lf_page_returns_text_unchanged` |
| 3 [R3] | `test_two_separate_edits_keep_crlf_on_every_line_between_them`, `test_replaced_lines_keep_their_own_end_on_a_mixed_page`, `test_a_merged_line_keeps_the_first_replaced_lines_end[crlf-then-lf,lf-then-crlf]` |
| 4 [R4] | `test_an_added_line_gets_the_most_used_end[all-crlf,3-crlf-1-lf,1-crlf-3-lf,2-2-tie]`, `test_an_original_last_line_that_gains_an_end_gets_the_most_used_end[most-used-crlf,most-used-lf]`, `test_a_text_without_a_final_line_end_gets_none` |
| 5 [R2-R4] | `test_random_multi_edits_keep_the_text_and_the_page_ends` (seed 175, 3,000 cases, 1,000 each all-CRLF / all-LF / mixed), `test_a_5000_line_crlf_page_with_50_edits_restores_in_under_5_seconds` (0.65 s call locally) |
| 6 [R5] | DoD: all 27 `tests/test_kbfix_linker_crlf.py` tests and every other DoD file pass; `git diff --name-only origin/main...HEAD -- tests/` lists only `tests/test_kbfix_line_ends.py`; `grep -cE '_read_page\|_restore_line_ends\|_LINE_END_RE' src/kb/compile/linker.py` = 0; linker line 10 `from kb.utils.line_ends import read_page_text, restore_line_ends`; `kb.utils.line_ends` has no `kb` import |
| 7 | `docs/reference/architecture.md` (Wikilink injection bullet), `docs/reference/module-map.md` (Line ends bullet), one entry each in `CHANGELOG.md` and `CHANGELOG-history.md`, `CLAUDE.md` State "3904 tests across 223 test files" (verify_docs above) |

### Finding for the lead (not changed on this branch)
The plain `SequenceMatcher` alignment R3 names can pair a later duplicate line as `equal` and treat the edited line as added. Reproducer (mixed page, one in-line link splice on line 7, whose text "matters" also ends the page):
`restore_line_ends('matters\n\n\n\nx Hydration\n x \n[[t|T]]ters\nmatters', 'matters\n\n\n\nx Hydration\n x \nmatters\nmatters', ['\n','\n','\n','\n','\r\n','\n','\r\n'])` gives `...\n[[t|T]]ters\nmatters`: the edited line loses its own CRLF and takes the most-used LF. The #174 restore kept CRLF. In a 20,000-case differential of single link splices on random mixed pages, 2 of 8,147 within-line splices differ this way; matching common leading and trailing lines before running `SequenceMatcher` on the middle removes both (8,147 of 8,147 equal to #174). All-CRLF and all-LF pages are not affected. This follows R3's literal text, so it is reported for a card amendment on main rather than changed here. Splices that span a line end differ from #174 by design (acceptance 3: a merged line keeps the FIRST replaced line's end; #174 kept the last).

### Budget
`git diff --stat origin/main...HEAD` before this entry: 8 files, +269 / -48. Of that, the new test file is 190 lines, the module 60, the linker -46 / +1, docs +14 / -2.

### Attempt 2 (implementer, 2026-11-16, card amended on main at badd5ee)

- Base sync: `git fetch origin && git merge --no-edit origin/main` gave merge commit 2f54b2a (origin/main badd5ee); the card file merged without conflict, main's amended text with the attempt-1 evidence below it. origin/main is still badd5ee at this entry.
- Commits: 66c32e6 RED amended acceptance 3 and 5; d5efceb GREEN `restore_line_ends` amended; e49bf85 docs; this entry.
- Attempt 1's section above is history: its finding is what the amendment fixed; the "a merged line keeps the first replaced line's end" rule it tested is replaced.

#### RED receipt
- At 66c32e6, `src/` identical to cd11126 (`git diff --quiet cd11126 HEAD -- src/`): `python -m pytest tests/test_kbfix_line_ends.py -q -p no:cacheprovider --tb=line` exit 1, `6 failed, 14 passed in 1.87s`, every failure an `AssertionError`:
  - `test_a_merged_line_keeps_the_second_lines_end[crlf-then-lf]`, `[lf-then-crlf]`
  - `test_a_split_line_gives_the_first_part_the_most_used_end_and_the_second_its_own[lf-line-on-crlf-page]`, `[crlf-line-on-lf-page]`
  - `test_an_edited_line_whose_old_text_recurs_later_keeps_its_own_end`
  - `test_single_splices_on_mixed_pages_give_the_one_splice_restores_bytes`

#### DoD receipt
- Exact `dod_command`, worktree root, main checkout `.venv\Scripts` first on PATH, at d5efceb: exit 0. `ruff check src/ tests/`: `All checks passed!`; pytest: `213 passed in 14.64s`. Output sha256 prefix 455200ccad760a75.
- Full suite at d5efceb (`python -m pytest -q -p no:cacheprovider`): exit 0, `3862 passed, 29 skipped, 17 xfailed, 54 warnings in 209.92s` (3908 collected). e49bf85 and this entry change no code or test.
- `python scripts/verify_docs.py` at e49bf85: `pytest collected tests = 3908`, `test file count = 223`, `OK - docs in sync.`

#### Oracle differential
- Committed: `test_single_splices_on_mixed_pages_give_the_one_splice_restores_bytes`, seed 174, 3,000 single splices on mixed pages (both CRLF and LF present, with and without a final line end, splice length 0-20, inserted text from a no-LF list including duplicates of page lines): every case equals the PR 174 restore copied into the test file.
- Scratch (not committed, same probe as attempt 1): 20,000 draws, 19,874 non-empty single link splices on random mixed pages: 0 differ from #174 (attempt 1: 3,510 differed, 2 of them within one line).

#### Acceptance map
| Item | Proof |
|---|---|
| 1 [R1] | `test_read_page_text_gives_read_text_and_the_line_ends`, `test_read_page_text_without_a_line_end_gives_no_ends` |
| 2 [R2] | `test_lf_page_returns_text_unchanged` |
| 3 [R3] | `test_two_separate_edits_keep_crlf_on_every_line_between_them`, `test_replaced_lines_keep_their_own_end_on_a_mixed_page`, `test_a_merged_line_keeps_the_second_lines_end[crlf-then-lf,lf-then-crlf]`, `test_a_split_line_gives_the_first_part_the_most_used_end_and_the_second_its_own[lf-line-on-crlf-page,crlf-line-on-lf-page]`, `test_an_edited_line_whose_old_text_recurs_later_keeps_its_own_end` (the card's exact `original`, ends and seventh-line edit) |
| 4 [R4] | `test_an_added_line_gets_the_most_used_end[all-crlf,3-crlf-1-lf,1-crlf-3-lf,2-2-tie]`, `test_an_original_last_line_that_gains_an_end_gets_the_most_used_end[most-used-crlf,most-used-lf]`, `test_a_text_without_a_final_line_end_gets_none` |
| 5 [R2-R4] | `test_random_multi_edits_keep_the_text_and_the_page_ends` (seed 175, 3,000 cases), `test_single_splices_on_mixed_pages_give_the_one_splice_restores_bytes` (seed 174, 3,000 splices, oracle `_one_splice_restore`), `test_a_5000_line_crlf_page_with_50_edits_restores_in_under_5_seconds` (0.51 s call locally) |
| 6 [R5] | DoD: all 27 `tests/test_kbfix_linker_crlf.py` tests and every other DoD file pass; `git diff --name-only origin/main...HEAD -- tests/` lists only `tests/test_kbfix_line_ends.py`; `src/kb/compile/linker.py` holds none of `_read_page`, `_restore_line_ends`, `_LINE_END_RE` and imports both helpers from `kb.utils.line_ends` (line 10); `kb.utils.line_ends` has no `kb` import |
| 7 | `docs/reference/architecture.md` (Wikilink injection bullet: helper, leading/trailing rule, pairing from the end, added-line rule), `docs/reference/module-map.md` (Line ends bullet), one entry each in `CHANGELOG.md` and `CHANGELOG-history.md`, `CLAUDE.md` State "3908 tests across 223 test files" (verify_docs above) |

#### Diff size
`git diff --numstat origin/main...HEAD` before this entry: CHANGELOG-history.md 16/0, CHANGELOG.md 1/0, CLAUDE.md 1/1, docs/reference/architecture.md 1/1, docs/reference/module-map.md 1/0, specs/tasks/T1-KBFIX-LINEENDS.md 36/0, src/kb/compile/linker.py 7/46, src/kb/utils/line_ends.py 79/0, tests/test_kbfix_line_ends.py 261/0.
