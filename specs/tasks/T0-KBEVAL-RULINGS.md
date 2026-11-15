---
id: T0-KBEVAL-RULINGS
title: "`bench/knowledge/labels.jsonl` records the owner's rulings on the three label disagreements, and the `Labels` section of `docs/knowledge-baseline.md` states the figures recomputed from it"
status: todo
branch: T0-KBEVAL-RULINGS
worktree: D:\wt\llm-wiki-flywheel\T0-KBEVAL-RULINGS
allow_paths:
  - bench/knowledge/labels.jsonl
  - bench/knowledge/tests/test_baseline.py
  - docs/knowledge-baseline.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - specs/tasks/T0-KBEVAL-RULINGS.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_baseline.py -q
dod_exit: 0
requirements:
  - R1. In `bench/knowledge/labels.jsonl`, the three rows whose `labelA` and `labelB` differ (`summaries/llm-knowledge-bases` sentence 1, `concepts/resolution-state` sentence 3, `concepts/progressive-disclosure` sentence 0) shall have `final` `partly-supported` and `ownerRuled` true, the owner's rulings given in the session of 2026-11-15; every other field of every row shall be unchanged.
  - R2. The `Labels` section of `docs/knowledge-baseline.md` shall state `Rows with an owner ruling: <n>`, and that figure, `Rows with a null final`, the label-count table and the `final`-by-band table shall equal the counts recomputed from `labels.jsonl`.
  - R3. The report shall describe `final` as it now stands: no sentence says that no row has an owner ruling or that rows wait for one, and the rule the owner applied is stated (a sentence with one claim, qualifier or generalisation that the source does not state is `partly-supported`).
  - R4. `bench/knowledge/tests/test_baseline.py` shall check R2 against counts recomputed from `labels.jsonl`, and its number scan shall allow the owner-ruling count.
  - R5. `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` shall each carry one entry under this card id.
acceptance:
  - 1. `git diff origin/main...HEAD -- bench/knowledge/labels.jsonl` changes exactly the three rows of R1, and on each only `final` (null to `partly-supported`) and `ownerRuled` (false to true); `test_labels_are_in_the_closed_set_and_final_follows_the_rule` passes on the edited file. [R1] [dod arm 2]
  - 2. `test_baseline.py`: the `Rows with an owner ruling` figure equals the count of rows with `ownerRuled` true, and `Rows with a null final` equals the count of rows with a null `final`. [R2] [R4] [dod arm 2]
  - 3. Same file: every cell of the label-count table equals the count of that label for `labelA`, `labelB` and `final` (the `null` row: rows with a null `final`), and every cell of the `final`-by-band table equals the count of rows with that band and `final`, with each band row summing to the rows in that band. [R2] [R4] [dod arm 2]
  - 4. Same file: `test_every_number_in_the_report_comes_from_summary_or_labels` passes with the owner-ruling count in its allowed set. [R4] [dod arm 2]
  - 5. The report text meets R3 (reviewer-verified); both changelog files carry the entry; `git diff --numstat origin/main...HEAD -- src/kb templates tests pyproject.toml requirements.txt bench/knowledge/summary.json` is empty. [R3] [R5]
depends_on: []
budget: 300
sweep: "Six paths, one new (this card). `labels.jsonl` gets three edited rows; the report's `Labels` section and one sentence of `What these numbers do not show` change; `test_baseline.py` gains the table checks. Agreement and kappa do not change: they are computed from `labelA` and `labelB`, which this card does not touch."
forbid: [any change under src/kb/ templates/ or tests/, any change to bench/knowledge/summary.json, any change to `labelA` or `labelB` or to a row whose labels agree, sentence text or source text from `wiki/` or `raw/` in any committed file, a ruling the owner did not give, a number in the report not computed from summary.json or labels.jsonl]
non_goals: [relabelling rows where the two labellers agree, a new bench run, a verifier, a change to the `final` rule of T1-KBEVAL-BASELINE R3]
hygiene: "No bench run and no model call: the rulings come from the owner and the files are edited from the committed state."
doc_sync: CHANGELOG.md
---

# T0-KBEVAL-RULINGS

## Deliverable
The owner's rulings on the three rows of the trace label sample where the two labellers differ, recorded in `labels.jsonl`, and the `Labels` section of the baseline report brought in line with them. No behaviour change.

## Why
T1-KBEVAL-BASELINE left the three disagreements with a null `final` and named "a later card records the rulings" as a non-goal. The owner has now ruled, so the label sample has a `final` on every row.

## The rulings
Given by the owner in the Claude Code session of 2026-11-15, after reading each sentence beside the source passage it restates:

| Row | labelA (Claude) | labelB (gpt-6-astra) | Ruling | Reason given with the question |
|---|---|---|---|---|
| `summaries/llm-knowledge-bases` sentence 1 | supported | partly-supported | partly-supported | "replacing traditional RAG approaches" generalises one person's experience; the source does not say RAG is replaced in general |
| `concepts/resolution-state` sentence 3 | supported | partly-supported | partly-supported | "doc versioning" and "requires" are not in the source, which says "docs" and "is" |
| `concepts/progressive-disclosure` sentence 0 | partly-supported | supported | partly-supported | the table of contents, `docs/` and progressive disclosure are stated; "better agent performance" is not |

Rule applied: the label definition given to both labellers, under which a sentence with one claim, qualifier or generalisation that the source does not state is `partly-supported`.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_baseline.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence
Attempt 1. RED `29f8555`, GREEN `05010c9`. Tests: `bench/knowledge/tests/test_baseline.py`.

### Commits
- `29f8555` RED: the three rulings in `labels.jsonl` (edited by a script that checked each row's labels differ, `final` is null and `ownerRuled` is false, and that every unchanged line re-serialises byte-equal) plus three new tests; the report is not updated. Result: 4 failed, 18 passed, every failure an `AssertionError`: the existing null-final check (`assert 3 == 0`), the owner-ruling figure (missing), the label-count table (`partly-supported` final `2` against `5`) and the band table (`low`/`partly-supported` `2` against `5`).
- Control, same tests on the original `labels.jsonl` (stashed): 1 failed, 21 passed. The only failure is the owner-ruling figure, which the original report does not state; the two table tests pass, so they read the committed tables correctly before the change.
- `05010c9` GREEN: the `Labels` section, one sentence of `What these numbers do not show` and both changelog entries. 22 passed.

### Acceptance
| Item | Proving test or command | Result |
|---|---|---|
| 1 [R1] | `git diff origin/main...HEAD -- bench/knowledge/labels.jsonl` (3 lines; `final` and `ownerRuled` only); `test_labels_are_in_the_closed_set_and_final_follows_the_rule` | pass |
| 2 [R2] [R4] | `test_labels_section_states_owner_ruled_count_recomputed_from_labels`, `test_labels_section_states_agreement_kappa_and_null_count_recomputed_from_labels` | pass |
| 3 [R2] [R4] | `test_label_count_table_equals_counts_recomputed_from_labels`, `test_final_by_band_table_equals_counts_recomputed_from_labels` | pass |
| 4 [R4] | `test_every_number_in_the_report_comes_from_summary_or_labels` (allowed set now holds the owner-ruling count) | pass |
| 5 [R3] [R5] | reviewer; both changelog entries; `git diff --numstat origin/main...HEAD -- src/kb templates tests pyproject.toml requirements.txt bench/knowledge/summary.json` | empty; for review |

### Mutation checks (applied one at a time to the GREEN report, tests run, file restored; none committed)
| Mutation | Caught by |
|---|---|
| M1 band table `low`/`partly-supported` 5 to 4 | `test_final_by_band_table_equals_counts_recomputed_from_labels` |
| M2 `Rows with an owner ruling` 3 to 2 | `test_labels_section_states_owner_ruled_count_recomputed_from_labels` |
| M3 label table `partly-supported` final 5 to 6 | `test_label_count_table_equals_counts_recomputed_from_labels` |
| M4 band row `mid` deleted | `test_final_by_band_table_equals_counts_recomputed_from_labels` |

## Attempt 2 evidence
R3 (codex, decision 1/2) blocked `2e4c87b` with one finding: `table()` stored rows in a dict, so a second row with the same name overwrote the first, and a wrong `supported` row (or an all-zero `low` row) placed before the correct one passed every test. RED `394c9b8`, GREEN: the commit after it. Report and data unchanged from attempt 1.

### Commits
- `394c9b8` RED: the two table checks moved into `label_table_errors` and `band_table_errors` with the attempt-1 behaviour (dict, last row wins), plus `test_table_checks_reject_an_extra_row_placed_before_the_correct_one`, which inserts a wrong row and an exact copy before the correct row in each table. Result: 1 failed, 22 passed; the failure is `assert [] != []` (the wrong `supported` row passed).
- GREEN: `table()` returns every row in order as (name, cells) with repeated names kept; both checks report a repeated row name (and the band check a repeated column), and compare every row, so a wrong row is reported even where it is not repeated. Also `test_labels_section_states_each_figure_once`: the four Labels figures are each read with `re.search`, which takes the first match, so a second line with another value would pass the same way; the test requires each figure line exactly once and checks that a doubled `Rows with an owner ruling` line is reported. 24 passed.

### Findings
| Finding | Fix | Tests |
|---|---|---|
| 1 duplicate-table-rows-unchecked | `table()` keeps every row; `repeated()` names repeated rows and columns; every row is compared with its expected counts | `test_table_checks_reject_an_extra_row_placed_before_the_correct_one`, `test_label_count_table_equals_counts_recomputed_from_labels`, `test_final_by_band_table_equals_counts_recomputed_from_labels` |
| same class, figures | each Labels figure must be stated once | `test_labels_section_states_each_figure_once` |

### Acceptance
| Item | Proving test or command | Result |
|---|---|---|
| 1 [R1] | `git diff origin/main...HEAD -- bench/knowledge/labels.jsonl` (3 lines; `final` and `ownerRuled` only); `test_labels_are_in_the_closed_set_and_final_follows_the_rule` | pass |
| 2 [R2] [R4] | `test_labels_section_states_owner_ruled_count_recomputed_from_labels`, `test_labels_section_states_agreement_kappa_and_null_count_recomputed_from_labels`, `test_labels_section_states_each_figure_once` | pass |
| 3 [R2] [R4] | `test_label_count_table_equals_counts_recomputed_from_labels`, `test_final_by_band_table_equals_counts_recomputed_from_labels`, `test_table_checks_reject_an_extra_row_placed_before_the_correct_one` | pass |
| 4 [R4] | `test_every_number_in_the_report_comes_from_summary_or_labels` | pass |
| 5 [R3] [R5] | reviewer; both changelog entries; `git diff --numstat origin/main...HEAD -- src/kb templates tests pyproject.toml requirements.txt bench/knowledge/summary.json` | empty; for review |

### Mutation checks on the GREEN tests (each run against the committed report with one change; none committed)
| Mutation | Reported as |
|---|---|
| wrong `supported` row before the correct one | `row supported appears more than once`; `row supported is ['0', '0', '0'], expected ['38', '37', '36']` |
| exact copy of the `supported` row | `row supported appears more than once` |
| all-zero `low` row before the correct one | `row low appears more than once`; `low/supported is 0, expected 9` |
| exact copy of the `low` row | `row low appears more than once` |
| band header with `supported` twice | `column supported appears more than once` |
| second `Rows with an owner ruling` line | `Rows with an owner ruling: stated 2 times` |
