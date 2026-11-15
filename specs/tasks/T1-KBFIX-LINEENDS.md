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
  - R3. WHEN `ends` holds a CRLF, the function `restore_line_ends` shall give each line of `text` that a line diff (`difflib.SequenceMatcher`, `autojunk=False`, over the LF-split lines) aligns with an equal line of `original` that line's own end, and each line that replaces a line of `original`, paired in order within one replaced run, the replaced line's end.
  - R4. WHEN `ends` holds a CRLF, the function `restore_line_ends` shall give every other line of `text` that has a line end (an added line, or an original last line that had no end) the most-used end of `ends`, and LF on a tie.
  - R5. The linker (`inject_wikilinks`, `inject_wikilinks_batch`) shall read pages through `read_page_text` and write `restore_line_ends` of its result, with no copy of either (`_read_page`, `_restore_line_ends`, `_LINE_END_RE`) left in `kb.compile.linker`.
acceptance:
  - 1. `test_kbfix_line_ends.py`: a file holding CRLF, LF and lone CR line ends gives the text `Path.read_text(encoding="utf-8")` gives and the ends `["\r\n", "\n", "\n"]`; a file with no line end gives `[]`. [R1] [dod arm 2]
  - 2. Same file: on an all-LF `original`, an edit that adds, removes and replaces lines returns `text` unchanged (`is` the same object or equal). [R2] [dod arm 2]
  - 3. Same file: an all-CRLF page of 10 lines edited on line 2 and line 9 keeps CRLF on lines 3-8; on a mixed page a replaced LF line keeps LF and a replaced CRLF line keeps CRLF; a line merged from two lines keeps the first replaced line's end. [R3] [dod arm 2]
  - 4. Same file: an added line gets CRLF on an all-CRLF page, CRLF on a page with 3 CRLF and 1 LF, LF on a page with 1 CRLF and 3 LF, and LF on a 2/2 tie; an original last line with no end that gains one gets the most-used end, and a `text` with no final line end gets none. [R4] [dod arm 2]
  - 5. Same file, a seeded property test of at least 2,000 random multi-edit cases (pages of random CRLF/LF mixes, 1-5 edits each adding, removing or replacing lines): the result with CRLF turned to LF equals `text`, an all-CRLF page stays all-CRLF, an all-LF page returns `text`; and a 5,000-line CRLF page with 50 scattered edits restores in under 5 seconds on the DoD runner. [R2] [R3] [R4] [dod arm 2]
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

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_line_ends.py tests/test_kbfix_linker_crlf.py tests/test_kbfix_linker_headings.py tests/test_kbfix_code_mask_redos.py tests/test_cycle18_linker_lock.py tests/test_cycle19_inject_batch_e2e.py tests/test_cycle19_inject_wikilinks_batch.py tests/test_cycle81_page_lock.py tests/test_compile.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
