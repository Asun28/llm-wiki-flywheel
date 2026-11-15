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
