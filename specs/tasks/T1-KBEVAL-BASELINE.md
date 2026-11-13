---
id: T1-KBEVAL-BASELINE
title: "`docs/knowledge-baseline.md` reports the Phase 0 numbers from one run of the knowledge bench on the main checkout's `wiki/` and `raw/`, with the committed records and the two-labeller labels of the trace sample"
status: todo
branch: T1-KBEVAL-BASELINE
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-BASELINE
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - docs/knowledge-baseline.md
  - bench/knowledge/summary.json
  - bench/knowledge/labels.jsonl
  - bench/knowledge/tests/test_baseline.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - specs/tasks/T1-KBEVAL-BASELINE.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_baseline.py -q
dod_exit: 0
requirements:
  - R1. `bench/knowledge/summary.json` shall hold, under `records`, the seven records of one run of `python bench/knowledge/run.py --wiki wiki --raw raw` on the main checkout that exited 0, keyed by probe name, and under `run` the commit of that run, the count of page files under `wiki/` and the count of files under `raw/`.
  - R2. `bench/knowledge/labels.jsonl` shall hold one row per line of that run's `trace-sample.jsonl`, with `page`, `sentence_index`, `start`, `end`, `sha256`, `band`, `labelA`, `labelB`, `final` and `ownerRuled`, and no sentence text.
  - R3. Each of `labelA` (Claude) and `labelB` (a model of another vendor, given the sentence and the text of the page's listed sources, and not `labelA`) shall be one of `supported`, `partly-supported`, `unsupported` and `not-a-claim`; `final` is their value when they are equal, the owner's value with `ownerRuled` true when the owner has ruled, and null otherwise.
  - R4. `docs/knowledge-baseline.md` shall have the sections `Method`, `Corpus and gaps`, `Invariants`, `Contradiction detection`, `Retrieval`, `Auto-links`, `Citations`, `Traceability`, `Labels`, `Rebuild`, `Provenance`, `Leads` and `What these numbers do not show`, in that order.
  - R5. Every number in `baseline.md` that comes from a record shall be written beside its key as `` `<probe>.<arm>.<metric>` `` and equal its value in `summary.json`, and the document shall state the commit of the run, the two corpus counts, every `unmeasured` arm with its reason, the raw agreement rate and Cohen's kappa of `labelA` and `labelB`, and the count of rows whose `final` is null.
  - R6. The `Invariants` section shall hold one row for each of I1 to I11 with the metrics that measure it, or `unmeasured` with the reason; I5 and I7 are `unmeasured`.
  - R7. The `Leads` section shall state, for each of the eight leads of `intent/kb-baseline.md`, the metrics that bear on it and one of `confirmed`, `contradicted` and `not decided`, and the document shall give no target and no recommendation for a later phase.
  - R8. `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` shall each carry one entry for `bench/knowledge/` and `docs/knowledge-baseline.md` under this card id.
acceptance:
  - 1. `test_baseline.py`: `summary.json` parses; `run.commit` is 40 hex characters; `records` has exactly the keys `citations`, `contradiction`, `linker`, `provenance`, `rebuild`, `retrieval` and `trace`; each record has the five keys of the record shape and at least one arm. [R1] [dod arm 2]
  - 2. Same file: every line of `labels.jsonl` parses with exactly the ten keys of R2; the row count equals `records.trace.arms.containment.metrics.sample_sentences`; `sha256` is 64 hex characters. [R2] [dod arm 2]
  - 3. Same file: `labelA` and `labelB` are in the closed set; `final` equals them when they are equal, is in the closed set when `ownerRuled` is true and is null otherwise. [R3] [dod arm 2]
  - 4. Same file: `baseline.md` has the thirteen headings of R4 in order; every backticked `<probe>.<arm>.<metric>` in it is a path in `summary.json`; the `Invariants` section holds the ids I1 to I11, each once. [R4] [R5] [R6] [dod arm 2]
  - 5. Same file: the raw agreement rate and Cohen's kappa recomputed from `labels.jsonl` equal the two figures in the `Labels` section to two decimals. [R5] [dod arm 2]
  - 6. The numbers of `baseline.md` equal `summary.json`, every `unmeasured` arm is stated with its reason, each lead carries one of the three verdicts with the metrics behind it, and no target or recommendation is stated (reviewer-verified against the diff). [R5] [R7]
  - 7. Both changelog files carry the entry; `git diff --numstat origin/main...HEAD -- src/kb templates tests pyproject.toml requirements.txt` is empty. [R8]
depends_on: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-LINKER, T1-KBEVAL-CITATIONS, T1-KBEVAL-TRACE, T1-KBEVAL-REBUILD, T1-KBEVAL-PROVENANCE]
budget: 900
sweep: "Seven paths, five of them new. `summary.json` and `labels.jsonl` are produced by the merged probes on the main checkout's own `wiki/` and `raw/`, which are untracked and exist only there, so the run is made on the main checkout and its two outputs are copied into the worktree. `CHANGELOG.md` and `CHANGELOG-history.md` follow the doc update checklist of `CLAUDE.md`; no test count changes because `tests/` is not touched."
forbid: [any change under src/kb/ templates/ or tests/, sentence text or source text from `wiki/` or `raw/` in any committed file, editing `summary.json` by hand, editing a label by hand except the `final` and `ownerRuled` fields of a row the owner ruled on, a number in baseline.md not computed from summary.json or labels.jsonl, a target or recommendation for a later phase, a second run chosen because its numbers read better]
non_goals: [waiting for the owner's rulings on label disagreements (rows stay with a null `final` and are counted; a later card records the rulings), labels on query answers, external labelled data sets, a trained verifier, probes for I5 and I7]
hygiene: "Run the bench once on the main checkout with its `.venv` active and keep the raw output under `_local/knowledge/`. The labels cost model spend: at most 20 USD for this goal (intent, Decisions). The vector arm of `retrieval` is measured only if the embedding model is on this machine's disk; do not download it for this card."
doc_sync: CHANGELOG.md
---

# T1-KBEVAL-BASELINE

## Deliverable
The baseline report and the two data files behind it. No behaviour change and no targets.

## Why
The targets for the fixes are set from this report and approved by the owner before any fix starts. A number in it has to be traceable to a record, and the labels are the only measure of support that later changes can be compared against.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_baseline.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
