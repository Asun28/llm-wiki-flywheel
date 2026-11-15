---
id: T1-KBFIX-FROMHEAD
title: "The linker never inserts a wikilink inside an ATX heading, and ingest writes the `### From` source ref as inline code (#161)"
status: todo
branch: T1-KBFIX-FROMHEAD
worktree: D:\wt\llm-wiki-flywheel\T1-KBFIX-FROMHEAD
plan_ref: plans/kb-defects-1.md#order-of-work
allow_paths:
  - src/kb/ingest/pipeline.py
  - src/kb/compile/linker.py
  - tests/test_kbfix_linker_headings.py
  - tests/test_backlog_by_file_cycle7.py
  - docs/reference/architecture.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T1-KBFIX-FROMHEAD.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_linker_headings.py tests/test_ingest.py tests/test_backlog_by_file_cycle7.py tests/test_compile.py tests/test_cycle18_linker_lock.py tests/test_cycle19_inject_wikilinks_batch.py tests/test_cycle19_inject_batch_e2e.py -q
dod_exit: 0
requirements:
  - R1. WHEN ingest appends a `### From <source_ref>` subsection to an existing `## Context` section, the heading shall be `### From ` followed by the source ref as one CommonMark inline code span, delimited by one backtick when the ref holds none, else by a backtick run one longer than the longest run in the ref with one space inside each delimiter.
  - R2. `inject_wikilinks` and `inject_wikilinks_batch` shall leave every ATX heading line (0-3 spaces of indent, 1-6 `#`, then a space, a tab or the end of the line) byte-identical, in the pre-lock peek and in the locked rewrite, while still linking the title in body text of the same page.
  - R3. `_mask_code_blocks` shall return the same result as before this card for every input; it stays the shared helper of ingest Context/References editing and the dead-links lint.
acceptance:
  - 1. `test_kbfix_linker_headings.py`: a page with a `## Context` section re-ingested from `raw/articles/second.md` (supplied extraction, no model call) gains the heading ``### From `raw/articles/second.md` ``; a ref holding one backtick and a ref holding two consecutive backticks each render as one code span (checked by parsing the heading with `markdown-it-py`: one `code_inline` token whose content is the ref). [R1] [dod arm 2]
  - 2. Same file: a page holding `### From raw/articles/high-hydration.md` and the body sentence `Hydration matters.` linked for title `Hydration`: the heading line is byte-identical and the body holds the wikilink, once through `inject_wikilinks` and once through `inject_wikilinks_batch`. [R2] [dod arm 2]
  - 3. Same file: headings of levels 1 to 6, indented 0 to 3 spaces, and one with closing `#`s, each containing the title, stay byte-identical after injection. [R2] [dod arm 2]
  - 4. Same file: a page whose only occurrence of the title is inside a heading is not written (bytes and mtime unchanged), so the pre-lock peek also ignores headings. [R2] [dod arm 2]
  - 5. Same file: `_mask_code_blocks` on a sample with headings, fenced and inline code, links and images returns the masked list without any heading line, equal to a literal expected value. The existing ingest Context/References tests in the DoD (incl. `test_appends_from_subsection_on_reingest`, `test_no_duplicate_context_section`, `test_references_regex_handles_whitespace_only_lines`) pass; the only edit to an existing test is the one R1 forces: `tests/test_backlog_by_file_cycle7.py:265` asserts the inline-code heading ``### From `raw/articles/b.md` `` instead of the bare path (the only existing assertion on `### From` text in `tests/`). [R1] [R3] [dod arm 2]
  - 6. The `Wikilink injection` bullet of `docs/reference/architecture.md` states that headings are not linked; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: [T1-KBFIX-TPLBASE]
budget: 250
sweep: "Nine paths: two src files, one new and one existing test file, four doc files, this card. `grep -rn '### From' tests/` finds one assertion on the heading text (test_backlog_by_file_cycle7.py:265), updated for R1. `_mask_code_blocks` callers: linker.py:231, :268 (inject_wikilinks peek + locked), :480, :512 (inject_wikilinks_batch peek + locked), pipeline.py:873, :915 (References / Context editing), lint/checks/dead_links.py:82. Only the four linker sites get the heading mask. A pre-plan experiment that masked headings inside `_mask_code_blocks` failed 5 ingest tests and no linker or dead-link test. `### From` is written at one place, pipeline.py:926; no code in src/ parses it."
forbid: [masking headings inside `_mask_code_blocks`, any change to dead-link lint results, rewriting `### From` headings already on disk, a model call or network request in tests]
non_goals: [Setext headings (underlined `===` / `---`; wiki pages use ATX), headings inside indented code blocks (4+ spaces; unchanged), linker title disambiguation and case sensitivity (lead 3, separate), a lint fix that converts old bare `### From` paths]
diagnosis:
  root_cause: "Ingest writes the raw path bare in `### From {source_ref}` (pipeline.py:926), and the injection mask covers only code, links and images (`_CODE_MASK_RE`, linker.py:46). Title matching is case-insensitive with `-` as a word boundary, so `Hydration` matches inside `high-hydration`."
  same_class: "Other generated headings that may hold a title: `## Context`, `## References`, page H1s; the heading mask covers all of them on the injection path. The dead-links lint shares `_mask_code_blocks` but reads links and does not write; it is unchanged by design (R3)."
hygiene: "Run the DoD with the main checkout's `.venv` active. RED: acceptance 1-4 fail on the unfixed code on the heading bytes, not with an import or collection error. Base this card on main after T1-KBFIX-TPLBASE merges (both edit `src/kb/ingest/pipeline.py`)."
doc_sync: docs/reference/architecture.md
---

# T1-KBFIX-FROMHEAD

## Deliverable
Wikilink injection never edits a heading line, so source paths in `### From` headings stay valid on new and on already-written pages, and new `### From` headings carry the source ref as inline code.

## Why
Issue #161. The rebuild probe saw `### From raw/articles/high-[[concepts/hydration|Hydration]].md`: a heading path broken by the linker.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_linker_headings.py tests/test_ingest.py tests/test_backlog_by_file_cycle7.py tests/test_compile.py tests/test_cycle18_linker_lock.py tests/test_cycle19_inject_wikilinks_batch.py tests/test_cycle19_inject_batch_e2e.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED commit `9ba84d3`, GREEN commit `bcae87b`. Tests: `tests/test_kbfix_linker_headings.py` (16 tests; ingest with a supplied extraction and `_skip_vector_rebuild=True`, no model call or network).

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. re-ingest from `raw/articles/second.md` writes ``### From `raw/articles/second.md` ``; refs with one and two backticks render as one code span (markdown-it-py: one `code_inline`, content = ref) | `test_reingest_writes_from_heading_with_inline_code_ref`, `test_from_heading_ref_is_one_code_span[no-backtick,one-backtick,two-backticks]` | pass |
| 2. `### From raw/articles/high-hydration.md` byte-identical, `Hydration matters.` linked, through both injectors | `test_from_heading_kept_while_body_is_linked[single,batch]` | pass |
| 3. heading levels 1-6, indent 0-3, closing `#`s byte-identical | `test_all_atx_heading_forms_stay_byte_identical[single,batch]` (fixtures checked as headings by `test_heading_fixtures_are_commonmark_headings`) | pass |
| 4. page matching only in headings: bytes and mtime unchanged (peek ignores headings) | `test_page_matching_only_in_headings_is_not_written[single,batch]` | pass |
| 5. `_mask_code_blocks` sample equals a literal (no heading masked); existing ingest Context/References tests pass; only edit to an existing test is `test_backlog_by_file_cycle7.py:265` | `test_mask_code_blocks_does_not_mask_headings`; DoD arm 2 (`git diff main -- tests/` touches the new file and that one line) | pass |
| 6. architecture bullet, one CHANGELOG / CHANGELOG-history entry each, CLAUDE.md State counts | `python scripts/verify_docs.py`: "docs in sync"; collected 3815, test files 218; State line reads `3815 tests across 218 test files` | pass (reviewer-verified) |

RED against the unfixed code (`main` at `28e3b4e`): 12 failed, 4 passed. All 12 failures are `AssertionError` (heading text bare instead of inline code; heading bytes rewritten to `high-[[concepts/hydration|Hydration]].md`; `['entities/bread'] == []` for the heading-only page). No import or collection error. The 4 passes guard behaviour the unfixed code already met: the CommonMark fixture check, both `#tag` controls, and the `_mask_code_blocks` literal (R3 regression guard). GREEN: DoD exit 0, `307 passed`.

| Input form | Covering test | Result |
|---|---|---|
| heading levels 1-6 | `test_all_atx_heading_forms_stay_byte_identical` | pass |
| indent 0-3 spaces | `test_all_atx_heading_forms_stay_byte_identical` | pass |
| closing `#`s; tab after `#` | `test_all_atx_heading_forms_stay_byte_identical` | pass |
| heading holding inline code (code placeholder inside heading restored) | `test_heading_holding_inline_code_is_restored_fully[single,batch]` | pass |
| `#tag` without space is not a heading, still linked | `test_hash_without_space_is_not_a_heading[single,batch]` | pass |
| ref with 0 / 1 / 2 backticks | `test_from_heading_ref_is_one_code_span[no-backtick,one-backtick,two-backticks]` | pass |

Recogniser differential (not committed): `_ATX_HEADING_RE.fullmatch` vs markdown-it-py `heading_open` on 616 generated lines (indent 0-4 spaces and tabs, 0-8 `#`, ten tails incl. empty, tab, closing `#`, escaped `#`, NBSP): 0 disagreements. `_inline_code` vs markdown-it-py on 8 refs (leading/trailing backtick, runs of 1-3, backtick-only refs): 0 disagreements.

Mutation (not committed): heading mask moved inside `_mask_code_blocks`. Result over the new file, `test_ingest.py`, `test_backlog_by_file_cycle7.py`, `test_lint.py`: 10 failed, 280 passed, incl. `test_mask_code_blocks_does_not_mask_headings` (acceptance-5 literal), 3 ingest Context/References tests, 2 cycle-7 tests. `src/kb/compile/linker.py` restored to the GREEN version afterwards.

Extra check: lint test files that mention dead links (`test_lint.py`, `test_lint_checks_split.py`, `test_lint_fix_v093.py`, `test_lint_runner.py`): 95 passed, 1 skipped.
