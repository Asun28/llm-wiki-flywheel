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
depends_on: [T1-KBEVAL-HARNESS-2]
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
