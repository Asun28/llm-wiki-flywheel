---
id: T1-KBEVAL-LINKER
title: "The `linker` probe reports precision and recall of `inject_wikilinks` on a committed labelled case set, in total and per category"
status: todo
branch: T1-KBEVAL-LINKER
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-LINKER
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/linker.py
  - bench/knowledge/data/linker/cases.jsonl
  - bench/knowledge/tests/test_linker.py
  - specs/tasks/T1-KBEVAL-LINKER.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_linker.py -q
dod_exit: 0
requirements:
  - R1. `cases.jsonl` shall hold one JSON object per line with `id` (unique), `category`, `title`, `target_id`, `body`, `should_link` and `why`, with at least 10 rows in each of six categories. `should_link` true, `proper-mention` (an English body names the titled thing) and `cjk-in-cjk` (a title in Chinese characters inside a Chinese sentence, with a Chinese character on each side of it). `should_link` false, `common-word` (the title is also an ordinary English word and the body uses the ordinary word), `case-variant` (the body holds the title's letters in another case with another meaning), `inside-code` (the title occurs only inside inline code or a fenced block), `already-linked` (the body already holds a wikilink to `target_id`).
  - R2. IF a line is not a JSON object, lacks a field, repeats an `id`, or holds a `category` outside the six or a `should_link` that is not its category's value, THEN the probe shall raise `ValueError` naming the file and the line number.
  - R3. For each row the probe shall make a wiki under `ctx.tmp` with one page of `target_id` and `title` and one page whose body is `body`, call `kb.compile.linker.inject_wikilinks(title, target_id, wiki_dir)`, and count the row as linked when the second page holds more wikilinks to `target_id` after the call than before it.
  - R4. The arm `inject` shall report `cases` and the metrics `tp`, `fp`, `fn`, `tn`, `precision`, `recall` and, for each category, `rows_<category>` and `linked_<category>`, where positive is `should_link` true and a ratio with a zero denominator is 0.
  - R5. The probe shall return `invariants` equal to `["I11"]`.
acceptance:
  - 1. `test_linker.py`: the committed `cases.jsonl` loads under R1 and R2, every category has at least 10 rows, and every `cjk-in-cjk` title has a Chinese character directly before and after it in the body. [R1] [dod arm 2]
  - 2. Same file, one test per cause of R2: `ValueError` whose message holds the file name and the line number. [R2] [dod arm 2]
  - 3. Same file, a four-row fixture with `inject_wikilinks` replaced by a stub that edits the page for chosen rows: the arm reports the hand-computed `tp`, `fp`, `fn`, `tn`, `precision`, `recall`, `rows_<category>` and `linked_<category>`; a row whose body already held one link and holds one after the call is not linked. [R3] [R4] [dod arm 2]
  - 4. Same file, the committed set run through the runner with the real function: exit 0, the arm `measured`, `cases` equal to the row count, `tp + fp + fn + tn` equal to `cases`, `invariants` equal to `["I11"]`. [R3] [R4] [R5] [dod arm 2]
  - 5. Each row's `why` names what the body text means, and each `common-word` and `case-variant` body uses the word in its other meaning (reviewer-verified against the diff). [R1]
depends_on: [T1-KBEVAL-HARNESS-3]
parallelizable_with: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-CITATIONS, T1-KBEVAL-TRACE, T1-KBEVAL-REBUILD, T1-KBEVAL-PROVENANCE]
budget: 450
forbid: [any change under src/kb/ templates/ or tests/, a model call or network request, a threshold or pass/fail judgement on precision or recall, removing or relabelling a row because of what `inject_wikilinks` did with it]
non_goals: [`inject_wikilinks_batch` (same pattern builder, not measured here), the effect of a wrong link on PageRank or search ranking, links on the owner's real wiki (no labels exist for them), a Chinese title next to Latin letters or digits, any fix]
hygiene: "`inside-code` and `already-linked` are controls the current code is expected to pass; they stay in the set so a later change to the matcher is checked against them. Write the case set before the first run. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-LINKER

## Deliverable
The first number for lead 3 of `intent/kb-baseline.md` and for invariant I11: how often an inserted link is wrong, and how often a Chinese title is missed.

## Why
`_build_title_pattern` compiles `\b<title>\b` with `re.IGNORECASE` and no disambiguation. The lead says a title such as "Go" links from "we go ahead", and that `\b` does not separate a Chinese title from the Chinese characters around it. Wrong links become graph edges that ranking reads, so the precision of the linker bounds the quality of the graph.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_linker.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence
Attempt 1.

RED/GREEN pair:
- RED `f0daa79:bench/knowledge/tests/test_linker.py`. The commit holds the case set, the tests and a stub probe that keeps `run(ctx)` and returns `invariants` `[]` and the arm `inject` `measured` with `cases` 0 and empty `metrics`; it reads no case set and calls no `kb` function. Result: 39 failed, 3 passed. Every failure is an assertion: 32 `DID NOT RAISE ValueError` (acceptance 2) and 7 `AssertionError` (`assert 0 == 72` for the committed set through the probe, the two four-row metric dicts, the zero-ratio dict, the call list `[] == [...]`, `assert 0 == 4` calls in the page-layout test, `[] == ['I11']` in the runner test). The 3 passes read `cases.jsonl` directly and do not use the probe.
- GREEN `f18aefa`: the real probe. Result: 42 passed.

The case set (72 rows, 12 per category) was written and labelled from meaning before the real probe ran on it; no row was edited after the run.

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. committed set loads under R1 and R2, >= 10 rows per category, each `cjk-in-cjk` title has a Chinese character directly before and after it [R1] | `test_committed_case_set_has_seven_fields_unique_ids_and_ten_rows_per_category`, `test_every_cjk_title_is_chinese_with_a_chinese_character_before_and_after_each_use` (checks every occurrence, not any), `test_english_rows_hold_the_title_in_the_form_their_category_names`, `test_committed_case_set_loads_through_the_probe_without_error` | pass |
| 2. one `ValueError` per cause of R2, naming file and line [R2] | `test_line_that_is_not_a_json_object_...`, `test_row_missing_a_field_...` (each of the 7 fields), `test_repeated_id_...`, `test_unknown_category_...`, `test_should_link_that_is_not_the_categorys_value_...` (each of the 6 categories) | pass |
| 3. four-row fixture with a stub that edits the page for chosen rows; hand-computed metrics; a row that held one link and holds one after is not linked [R3] [R4] | `test_inject_arm_reports_hand_computed_counts_ratios_and_per_category_rows` (row r4 is edited without a new link and counts as `tn`), `test_inject_arm_keeps_false_positives_and_misses_apart`, `test_fixture_with_no_positive_row_and_no_link_reports_zero_ratios`, `test_inject_is_called_once_per_row_with_title_target_and_wiki_dir`, `test_each_call_sees_a_fresh_wiki_with_the_target_page_and_the_body_page` | pass |
| 4. committed set through the runner with the real function [R3] [R4] [R5] | `test_runner_measures_the_inject_arm_on_the_committed_set`; `python bench/knowledge/run.py --probe linker` | pass; exit 0, no `guarded directory changed:` line |
| 5. each `why` names what the body means; `common-word` and `case-variant` bodies use the other meaning [R1] | reviewer reads `bench/knowledge/data/linker/cases.jsonl` | for review |

Measured on the committed set (`run.py --probe linker`): tp 12, fp 24, fn 12, tn 24, precision 0.3333333333333333, recall 0.5. Linked per category (of 12 rows each): proper-mention 12, cjk-in-cjk 0, common-word 12, case-variant 12, inside-code 0, already-linked 0.

Call cardinality: `test_inject_is_called_once_per_row_with_title_target_and_wiki_dir` records the stub's complete call list (positional and keyword arguments) and requires exactly one call per row, in row order, with three positional arguments `(title, target_id, wiki_dir)` and no keywords. `test_each_call_sees_a_fresh_wiki_with_the_target_page_and_the_body_page` checks, at each call, that `wiki_dir` is a distinct directory under `ctx.tmp` holding exactly two pages: `<target_id>.md` with frontmatter `title` equal to the row title, and one page in a `WIKI_SUBDIRS` directory whose body equals the row body.

Expected values come from hand-written literals (acceptance 3) or from counting rows in `cases.jsonl` (acceptance 1 and 4), never from the probe's output.

Mutation checks (each applied alone to `probes/linker.py`, tests run, file restored; none committed):

| Mutation | Result | Tests that caught it |
|---|---|---|
| M1 every row linked (constant result) | 3 failed | both four-row metric tests, zero-ratio test |
| M2 linked when the page text changed | 1 failed | `test_inject_arm_reports_hand_computed_...` (row r4) |
| M3 `inject_wikilinks` called twice per row | 2 failed | call-list test, page-layout test |
| M4 `should_link` check removed | 9 failed | the 6 category-value and 3 non-boolean rejection tests |
| M5 `fp` and `fn` swapped | 2 failed | `test_inject_arm_keeps_false_positives_and_misses_apart`, runner test |
| M6 one wiki directory for every row | 1 failed | page-layout test |
| M7 `linked_` counted only for positive rows | 3 failed | both four-row metric tests, runner test |

Input forms and failure paths the loader handles:
- valid line with the seven fields: `test_committed_case_set_loads_through_the_probe_without_error`
- line that is JSON but not an object: `test_line_that_is_not_a_json_object_is_rejected_with_file_and_line`
- line that is not JSON: `test_line_that_is_not_json_at_all_is_rejected_with_file_and_line`
- blank line (rejected as not JSON): `test_blank_line_is_rejected_with_file_and_line`
- missing field, each of the seven: `test_row_missing_a_field_is_rejected_with_file_and_line[<field>]`
- text field that is not a string, each of the six: `test_text_field_that_is_not_a_string_is_rejected_with_file_and_line[<field>]`
- repeated `id`: `test_repeated_id_is_rejected_with_file_and_line`
- unknown category: `test_unknown_category_is_rejected_with_file_and_line`
- `should_link` that is not the category's value, each of the six categories: `test_should_link_that_is_not_the_categorys_value_is_rejected[<category>]`
- `should_link` that is not a boolean (`"true"`, `1`, `null`): `test_should_link_that_is_not_a_boolean_is_rejected[<value>]`
- `target_id` that is not `<wiki subdir>/<slug>` (`../outside`, `concepts/../../x`, `Concepts/Alpha`, `alpha`, `notes/alpha`): `test_target_id_that_is_not_a_wiki_page_id_is_rejected[<value>]`. This rule is not in R2; it keeps the page the probe writes under `ctx.tmp`.
- zero denominator for precision and recall: `test_fixture_with_no_positive_row_and_no_link_reports_zero_ratios`

Design notes for the reviewer:
- `common-word` bodies use the word with the same capitalisation as the title (at the start of a sentence), so that category measures meaning alone; `case-variant` bodies hold the title only in another case (the test checks no exact-case occurrence).
- `already-linked` and `inside-code` bodies also hold the title outside the link or inside code, so the matcher has text to act on and the control is not passed trivially.
- Links are counted with `kb.utils.markdown.extract_wikilinks` over the whole body page.
