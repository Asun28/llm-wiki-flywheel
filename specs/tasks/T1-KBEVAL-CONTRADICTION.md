---
id: T1-KBEVAL-CONTRADICTION
title: "The `contradiction` probe reports precision and recall of `detect_contradictions` and of `_has_contradiction_signal` on a committed labelled case set, in total and per category"
status: todo
branch: T1-KBEVAL-CONTRADICTION
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-CONTRADICTION
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/contradiction.py
  - bench/knowledge/data/contradiction/cases.jsonl
  - bench/knowledge/tests/test_contradiction.py
  - specs/tasks/T1-KBEVAL-CONTRADICTION.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_contradiction.py -q
dod_exit: 0
requirements:
  - R1. `cases.jsonl` shall hold one JSON object per line with `id` (unique), `category`, `claim`, `existing`, `label` and `why`, with at least 10 rows in each of seven categories. Label `contradiction`, `negation` (one side negates the other), `both-negated` (both sides hold a negation word and state different things), `date` (two dates for one event), `number` (two counts or amounts for one quantity). Label `consistent`, `paraphrase` (one fact reworded, no negation word on either side), `negated-paraphrase` (one fact, one side phrased with a negation word), `unrelated-negation` (shared entities, one side negates a different fact).
  - R2. IF a line is not a JSON object, lacks a field, repeats an `id`, or holds a `category` outside the seven or a `label` that is not its category's label, THEN the probe shall raise `ValueError` naming the file and the line number.
  - R3. The arm `detect` shall call `kb.ingest.contradiction.detect_contradictions([claim], [{"id": id, "content": existing}])` once per row and count the row as flagged when the returned list is not empty.
  - R4. The arm `signal` shall call `kb.ingest.contradiction._has_contradiction_signal(claim, existing)` once per row and count the row as flagged when it returns true.
  - R5. Each arm shall report `cases` (the row count) and the metrics `tp`, `fp`, `fn`, `tn`, `precision`, `recall` and, for each category, `rows_<category>` and `flagged_<category>`, where positive is the label `contradiction` and a ratio with a zero denominator is 0.
  - R6. The probe shall return `invariants` equal to `["I10"]`.
acceptance:
  - 1. `test_contradiction.py`: the committed `cases.jsonl` loads under R1 and R2 and every category has at least 10 rows. [R1] [dod arm 2]
  - 2. Same file, one test per cause (a line that is not an object, a missing field, a repeated `id`, an unknown category, a label that is not the category's): `ValueError` whose message holds the file name and the line number. [R2] [dod arm 2]
  - 3. Same file, a four-row fixture with the two `kb` functions replaced by stubs with fixed answers: both arms report the hand-computed `tp`, `fp`, `fn`, `tn`, `precision`, `recall`, `rows_<category>` and `flagged_<category>`, and a fixture with no positive row reports `recall` 0. [R3] [R4] [R5] [dod arm 2]
  - 4. Same file, the committed set run through the runner with the real functions: exit 0, both arms `measured`, `cases` equal to the row count, `tp + fp + fn + tn` equal to `cases`, the `rows_` metrics summing to `cases`, `invariants` equal to `["I10"]`. [R3] [R4] [R5] [R6] [dod arm 2]
  - 5. Each row's `why` names the fact that makes its label true, and no label depends on knowledge outside the two texts (reviewer-verified against the diff). [R1]
depends_on: [T1-KBEVAL-HARNESS-3]
parallelizable_with: [T1-KBEVAL-RETRIEVAL, T1-KBEVAL-LINKER, T1-KBEVAL-CITATIONS, T1-KBEVAL-TRACE, T1-KBEVAL-REBUILD, T1-KBEVAL-PROVENANCE]
budget: 400
forbid: [any change under src/kb/ templates/ or tests/, a model call or network request, a threshold or pass/fail judgement on precision or recall, removing or relabelling a row because of what either function returned for it]
non_goals: [an external labelled set such as WikiContradict (a later goal), contradictions that need more than the two texts to see (not in the set), a separate metric for the token-overlap gate inside `detect_contradictions` (the `signal` arm bypasses it and the difference between the arms shows its effect), any fix]
hygiene: "Write the case set before running either function on it. After the first run a row changes only when its `why` shows the label was wrong, and the PR names each such row. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-CONTRADICTION

## Deliverable
The first number for lead 1 of `intent/kb-baseline.md`: how often the keyword check flags a real contradiction and how often it flags a consistent pair.

## Why
`_has_contradiction_signal` returns true when exactly one of the two texts holds a negation word. The lead says date and number conflicts pass and unrelated negations are flagged; four hand cases are not a measurement. Seven fixed categories with at least 10 rows each give a precision and a recall that a later replacement can be compared against on the same rows.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_contradiction.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence
Attempt 1. RED receipt `eea799a:bench/knowledge/tests/test_contradiction.py` (13 tests: 2 failed, 11 errors, all `FileNotFoundError` for the missing `cases.jsonl` or `probes/contradiction.py`). Blocked by R3: that RED ran no assertion.

Attempt 2. RED/GREEN pair:
- RED `bfa89c5:bench/knowledge/tests/test_contradiction.py`. The probe is a stub that keeps `run(ctx)` and returns both arms `measured` with `cases` 0 and every metric (`tp` to `recall`, all `rows_`/`flagged_` keys) at 0; it reads no case set and calls neither kb function. It is well-formed, so the runner accepts it and every behavioural test reaches its assertion. Result: 13 failed, 1 passed. Every failure is an assertion: 8 `DID NOT RAISE ValueError` (acceptance 2 and the extra loader cases), `assert 0 == 73` (committed set through the probe), the four-row metric dict, the call list `[] == [...]`, `(0, 0) == (1, 1)` (no-positive fixture), `AssertionError: detect` (runner `cases`). The one pass is `test_committed_case_set_has_six_fields_...`, which reads the data file directly and does not use the probe.
- GREEN: the commit after `bfa89c5` restores the probe byte for byte from `d27c3c4` and carries the row fixes below.

Call cardinality (R3 finding F2): `test_each_arm_calls_its_function_exactly_once_per_row_with_the_r3_r4_arguments` records each stub's full call list (positional and keyword arguments) and requires exactly one call per row per arm, in row order, with `([claim], [{"id": id, "content": existing}])` and `(claim, existing)`. Mutation check, not committed: with the probe changed to call each function a second time per row, this test fails (`1 failed, 13 passed`, the failure is the call-list assertion) and every attempt-1 test still passes.

Rows rewritten in attempt 2 (wording chosen from meaning alone, before either function ran on the new texts; ids, category `negated-paraphrase` and label `consistent` kept):

| Row | Old claim / existing | New claim / existing | Reason |
|---|---|---|---|
| np-08 (F3) | "The Quill editor stores drafts only on the local device." / "The Quill editor never sends drafts to a server; they stay on the local device." | "The Quill editor stores drafts only on the local device." / "The Quill editor does not store drafts anywhere other than the local device." | Old pair stated two facts: local storage allows sending drafts to a server for processing. New pair states one storage restriction. |
| np-10 (F4) | "From version 5 onward the Vireo cache uses the v2 format." / "From version 5 the Vireo cache no longer uses the v1 format and uses the v2 format instead." | "From version 5 the Vireo cache uses only the v2 format." / "From version 5 the Vireo cache does not use any format other than v2." | Old claim allowed v1 alongside v2; the existing text excluded v1. New pair states one format restriction. |
| np-03 (same defect, found in the check of the other negated-paraphrase rows) | "Standard user rights are enough to install the Brisk CLI." / "The Brisk CLI does not need administrator rights to install." | "Installing the Brisk CLI needs only standard user rights." / "Installing the Brisk CLI does not need any rights beyond standard user rights." | Old pair was equal only if administrator is the one level above standard user, which is knowledge outside the texts. New pair states one requirement. |

The other eight negated-paraphrase rows (np-01, 02, 04, 05, 06, 07, 09, 11) each state one fact twice and were left unchanged. Each rewritten row's `why` was updated.

Detector output on those rows, before and after the rewrite: np-03, np-08 and np-10 are each flagged by both arms before (`detect` True, `signal` True) and after (`detect` True, `signal` True). The totals did not change: tp 10, fp 22, fn 31, tn 10, precision 0.3125, recall 0.24390243902439024 for both arms.

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. committed set loads, >= 10 rows per category [R1] [R2] | `test_committed_case_set_has_six_fields_unique_ids_and_ten_rows_per_category`, `test_committed_case_set_loads_through_the_probe_without_error` | pass (73 rows: 11/10/10/10/10/11/11) |
| 2. one `ValueError` per cause, naming file and line [R2] | `test_line_that_is_not_a_json_object_...`, `test_row_missing_a_field_...`, `test_repeated_id_...`, `test_unknown_category_...`, `test_label_that_is_not_the_categorys_label_...` | pass |
| 3. hand-computed metrics with stubbed functions; no-positive fixture has recall 0 [R3] [R4] [R5] | `test_both_arms_report_hand_computed_counts_ratios_and_per_category_rows`, `test_each_arm_calls_its_function_exactly_once_per_row_with_the_r3_r4_arguments`, `test_fixture_with_no_positive_row_reports_zero_recall_and_zero_precision` | pass |
| 4. committed set through the runner with real functions [R3] [R4] [R5] [R6] | `test_runner_measures_both_arms_on_the_committed_set`; `python bench/knowledge/run.py --probe contradiction` | pass; exit 0, no `guarded directory changed:` line |
| 5. each `why` names the fact; no outside knowledge [R1] | reviewer reads `bench/knowledge/data/contradiction/cases.jsonl` | for review |

Input forms and failure paths the loader handles:
- valid line with the six string fields: `test_committed_case_set_loads_through_the_probe_without_error`
- line that is JSON but not an object: `test_line_that_is_not_a_json_object_is_rejected_with_file_and_line`
- line that is not JSON: `test_line_that_is_not_json_at_all_is_rejected_with_file_and_line`
- blank line (rejected as not JSON): `test_blank_line_is_rejected_with_file_and_line`
- missing field: `test_row_missing_a_field_is_rejected_with_file_and_line`
- field that is not a string: `test_field_that_is_not_a_string_is_rejected_with_file_and_line`
- repeated `id`: `test_repeated_id_is_rejected_with_file_and_line`
- unknown category: `test_unknown_category_is_rejected_with_file_and_line`
- label that is not the category's: `test_label_that_is_not_the_categorys_label_is_rejected_with_file_and_line`
- zero denominator for precision and recall: `test_fixture_with_no_positive_row_reports_zero_recall_and_zero_precision`
- each function called once per row with the R3/R4 arguments: `test_each_arm_calls_its_function_exactly_once_per_row_with_the_r3_r4_arguments`

Test correction after RED: `test_unknown_category_...` passed `category` to `row()` both by position and by keyword (a `TypeError` hidden at RED by the missing probe). Fixed to build the row and then override `category`; with the probe's category check removed the corrected test fails (`KeyError: 'sarcasm'`), with it present the test passes.

Attempt 3 (R3 decision 2 blocked para-08 and np-06 as category-not-paraphrase). Audit test for each `consistent` row: is there a world where one text is true and the other false (subject, time span, scope, modality, outside knowledge, and anything one text implies that the other leaves open)? For each `contradiction` row: is there a world where both are true? A row that failed was rewritten from meaning alone before either function ran on the new text; id, category and label kept, `why` names the one shared fact (or the two conflicting values). Detector output is `detect`/`signal`.

| Row | Old claim / existing | New claim / existing | Reason | Before | After |
|---|---|---|---|---|---|
| para-01 | "The Marlow Bridge opened in 1932." / "In 1932 the Marlow Bridge was opened to traffic." | unchanged / "The Marlow Bridge was opened in 1932." | Opening and opening to traffic can fall in different years. | F/F | F/F |
| para-07 | "The Corvid protocol encrypts messages end to end." / "Messages sent with the Corvid protocol are encrypted end to end." | unchanged / "Messages are encrypted end to end by the Corvid protocol." | The old passive left open who encrypts; an app could encrypt while the protocol does not. | F/F | F/F |
| para-08 | "Version 2.0 of the Vega compiler was released in March 2019." / "The Vega compiler reached version 2.0 in March 2019." | unchanged / "In March 2019 the Vega compiler version 2.0 was released." | Reaching 2.0 internally is not releasing it (cited). | F/F | F/F |
| para-09 | "The Fenwick museum is open on Mondays." / "On Mondays the Fenwick museum opens to visitors." | unchanged / "On Mondays the Fenwick museum is open." | Opening to visitors narrows who it is open to. | F/F | F/F |
| np-03 | "Installing the Brisk CLI needs only standard user rights." / "Installing the Brisk CLI does not need any rights beyond standard user rights." | "Installing the Brisk CLI requires standard user rights and only those rights." / "Installing the Brisk CLI requires standard user rights and does not require any other rights." | The old existing text left open whether standard rights are needed at all. | T/T | T/T |
| np-04 | "The Kestrel API accepts only JSON." / "The Kestrel API does not accept any format other than JSON." | "The Kestrel API accepts JSON and only JSON." / "The Kestrel API accepts JSON and does not accept any other format." | The old existing text left open whether JSON is accepted. | T/T | T/T |
| np-05 | "The Sable river stays liquid all winter." / "The Sable river never freezes in winter." | "The Sable river bridge is open on every day of the year." / "There is not a day of the year on which the Sable river bridge is closed." | Not freezing and staying liquid differ for a river that dries up; the new fact is a two-state one (open or closed). | T/T | T/T |
| np-06 | "The Gannet team switched from MySQL to Postgres in 2020." / "Since 2020 the Gannet team no longer uses MySQL and uses Postgres." | "From 2020 to 2023 the Gannet team used Postgres as its only database." / "From 2020 to 2023 the Gannet team used Postgres and did not use any other database." | A later switch back satisfies the claim and not the existing text (cited); both now share one span and one restriction. | T/T | T/T |
| np-07 | "The Pellam plugin requires Rook framework version 3 or later." / "The Pellam plugin does not run on Rook framework versions earlier than 3." | "The Pellam plugin runs on Rook framework version 3 or later and on those versions only." / "The Pellam plugin runs on Rook framework version 3 or later and does not run on any earlier version." | Requires (a stated condition) and does not run (behaviour) differ in modality. | T/T | T/T |
| np-08 | "The Quill editor stores drafts only on the local device." / "The Quill editor does not store drafts anywhere other than the local device." | "The Quill editor stores drafts on the local device and only there." / "The Quill editor stores drafts on the local device and does not store them anywhere else." | The old existing text left open whether drafts are stored at all. | T/T | T/T |
| np-10 | "From version 5 the Vireo cache uses only the v2 format." / "From version 5 the Vireo cache does not use any format other than v2." | "From version 5 the Vireo cache uses the v2 format and only that format." / "From version 5 the Vireo cache uses the v2 format and does not use any other format." | The old existing text left open whether v2 is used. | T/T | T/T |
| np-11 | "Tickets for the Wren festival are free." / "The Wren festival does not charge for tickets." | "Tickets for the Wren festival are free of charge." / "Tickets for the Wren festival do not cost anything." | A third party could charge for tickets that the festival does not charge for. | T/T | T/T |
| date-04 | "...first recorded the comet on 2 February 2003." / "...first recorded the comet on 11 October 2005." | "...first recorded comet K-17 on 2 February 2003." / "...first recorded comet K-17 on 11 October 2005." | "The comet" could be two different comets, so both could be true. | F/F | F/F |
| date-06 | "The Orrin dam was completed in 1967." / "Construction of the Orrin dam was completed in 1959." | unchanged / "The Orrin dam was completed in 1959." | Completion of construction and completion of the dam can differ, so both could be true. | F/F | F/F |
| date-10 | "The Carrow manuscript was dated to 1412." / "The Carrow manuscript was dated to 1530." | "The Carrow manuscript was written in 1412." / "The Carrow manuscript was written in 1530." | Two scholars can date one manuscript differently, so both could be true; a writing year is one fact. | F/F | F/F |

Checked, unchanged:
- paraphrase: para-02, para-03, para-04, para-05, para-06, para-10.
- negated-paraphrase: np-01, np-02, np-09.
- unrelated-negation (each pair can be true together): un-01 to un-11.
- negation: neg-01 to neg-11. both-negated: bn-01 to bn-10. date: date-01, 02, 03, 05, 07, 08, 09. number: num-01 to num-10.
- Note: both-negated, date and number hold no `consistent` row; their rows were checked with the both-true test instead.

Totals after attempt 3 are unchanged for both arms: tp 10, fp 22, fn 31, tn 10, precision 0.3125, recall 0.24390243902439024 (each rewritten row had the same flag before and after).

Attempt 1 changed no row after the first run of either function. Attempt 2 changed np-03, np-08 and np-10, and attempt 3 changed the 15 rows in its table, on review evidence, not on detector output.
