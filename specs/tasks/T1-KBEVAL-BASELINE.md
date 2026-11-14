---
id: T1-KBEVAL-BASELINE
title: "`docs/knowledge-baseline.md` reports the Phase 0 numbers from one run of the knowledge bench on the main checkout's `wiki/` and `raw/`, with the committed records and the two-labeller labels of the trace sample"
status: merged
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

## Attempt evidence
Attempt 1. RED `3d0b0b1`, GREEN: the commit after it on this branch. Tests: `bench/knowledge/tests/test_baseline.py`.

### Commits
- `3d0b0b1` RED: the tests plus well-formed, wrong placeholders: `summary.json` with the `run` keys and empty `records`, an empty `labels.jsonl`, and a `docs/knowledge-baseline.md` with no section headings and one record path that is not in the empty summary. Result: 14 failed, 1 passed; every failure is an `AssertionError`. The pass is `test_kappa_helper_matches_a_worked_example`, which checks the test's own kappa helper against a hand-worked example (p_o 0.6, p_e 0.5, kappa 0.2).
- GREEN: `summary.json` and `labels.jsonl` built by scripts (not committed) from the run below, the report, both changelog entries and this section. 15 passed.

### The run
- Command, from `D:\Projects\llm-wiki-flywheel` with its `.venv/Scripts` first on `PATH` and `HF_HUB_OFFLINE=1` (so the embedding model could not be downloaded): `python bench/knowledge/run.py --wiki wiki --raw raw --out _local/knowledge`, stdout and stderr in `_local/knowledge/run.log`.
- Exit code 0; no `guarded directory changed:` line. One run only.
- Commit `82ee29f3598308572d58f4b736e8140080c72f54`; every record has `dirty: true`. Cause: three untracked files outside `wiki/` and `raw/` (`.github/workflows/security-scanners.yml`, `demo/2026-05-22.md`, `demo/Untitled.canvas`); no tracked file modified.
- Corpus at the run: 183 `.md` files under `wiki/` (175 in subdirectories), 43 files under `raw/`.

### Labels
- labelA: Claude, after reading each sentence and the full text of the page's listed sources (for the DELEGATE-52 paper, the abstract and the passages the sentences restate). Written to `_local/knowledge/labelA.jsonl` before any labelB call.
- labelB: `codex exec -m gpt-6-astra --sandbox read-only --skip-git-repo-check --ephemeral -C <empty scratch dir> -o <out> -` with the prompt on stdin; one call per distinct source list (9 calls, 203,862 tokens in total as reported by the codex logs). Each prompt holds the four label definitions, the full text of the sources and the sentences of that source list, and asks for one JSON label per sentence. It never holds labelA. Each log reports `model: gpt-6-astra`, `provider: openai`. Prompts, outputs and logs: `_local/knowledge/labelB/`.
- n 56, raw agreement 0.9464 (0.95), Cohen's kappa 0.8875 (0.89), 3 rows with a null `final` (all `supported` against `partly-supported`), `ownerRuled` false on every row.

### Acceptance
| Item | Proving test or command | Result |
|---|---|---|
| 1 [R1] | `test_summary_holds_the_run_commit_and_the_seven_records_of_the_record_shape`, `test_summary_run_holds_the_dirty_flag_and_the_two_corpus_counts` | pass |
| 2 [R2] | `test_each_label_row_has_the_ten_keys_and_no_sentence_text`, `test_label_row_count_equals_the_trace_sample_size_of_the_run`, `test_label_rows_are_unique_per_page_and_sentence` | pass |
| 3 [R3] | `test_labels_are_in_the_closed_set_and_final_follows_the_rule` | pass |
| 4 [R4] [R5] [R6] | `test_report_has_the_thirteen_sections_in_order`, `test_every_backticked_record_path_in_the_report_is_in_summary`, `test_invariants_section_holds_i1_to_i11_once_each_with_i5_and_i7_unmeasured` | pass |
| 5 [R5] | `test_labels_section_states_agreement_kappa_and_null_count_recomputed_from_labels`, `test_kappa_helper_matches_a_worked_example` | pass |
| 6 [R5] [R7] | reviewer; also `test_every_record_number_in_the_report_equals_summary_to_four_decimals`, `test_report_states_the_run_commit_and_the_corpus_counts`, `test_every_unmeasured_arm_is_named_in_the_report_with_its_reason`, `test_leads_section_gives_each_of_the_eight_leads_one_verdict` | pass; for review |
| 7 [R8] | entries in `CHANGELOG.md` and `CHANGELOG-history.md`; `git diff --numstat origin/main...HEAD -- src/kb templates tests pyproject.toml requirements.txt` | empty |

### Mutation checks (applied one at a time to the GREEN files, tests run, file restored; none committed)
| Mutation | Caught by |
|---|---|
| M1 kappa in the report 0.89 to 0.88 | `test_labels_section_states_agreement_kappa_and_null_count_recomputed_from_labels` |
| M2 agreement 0.95 to 0.96 | same |
| M3 null-final count 3 to 2 | same |
| M4 `linker.inject.precision` written as 0.3334 | `test_every_record_number_in_the_report_equals_summary_to_four_decimals` |
| M5 I5 row marked measured | `test_invariants_section_holds_i1_to_i11_once_each_with_i5_and_i7_unmeasured` |
| M6 a lead verdict outside the three values | `test_leads_section_gives_each_of_the_eight_leads_one_verdict` |
| M7 one `labelB` changed in `labels.jsonl` | `test_labels_are_in_the_closed_set_and_final_follows_the_rule`, `test_labels_section_states_agreement_kappa_and_null_count_recomputed_from_labels` |

## Attempt 2 evidence
R3 (codex, decision 1/2) blocked `49c48a3` with 3 findings. RED `e96b09c`, GREEN: the commit after it. The bench was not rerun; `summary.json` and `labels.jsonl` are byte-equal to `49c48a3`.

### Commits
- `e96b09c` RED, run against the `49c48a3` data and report: 3 failed, 16 passed, every failure an `AssertionError`:
  - `test_final_rule_rejects_an_owner_ruling_that_overrides_agreed_labels` (`assert 0 == 1`): the new `final_rule_errors` helper still had the attempt-1 order (`ownerRuled` checked before agreement), so the fixture row `supported`/`supported`, `ownerRuled: true`, `final: unsupported` was accepted.
  - `test_every_record_number_in_the_report_is_the_exact_text_of_its_summary_value`: the rounded values (for example `0.2439` for `0.24390243902439024`).
  - `test_every_number_in_the_report_comes_from_summary_or_labels`: the stray numbers of the attempt-1 report.
- GREEN: agreement checked first in `final_rule_errors`; the report rewritten. 19 passed.

### Findings
| Finding | Fix | Tests |
|---|---|---|
| 1 agreed-final-override | `final_rule_errors` checks `labelA == labelB` first: `final` must equal them whatever `ownerRuled` says; an owner ruling is checked only for differing labels | `test_labels_are_in_the_closed_set_and_final_follows_the_rule` (committed file), `test_final_rule_rejects_an_owner_ruling_that_overrides_agreed_labels` (temporary fixture row), `test_final_rule_accepts_an_owner_ruling_on_differing_labels_and_null_without_one` (control rows) |
| 2 rounded-record-values | Every `` `probe.arm.metric` = value `` rewritten from `summary.json` as `json.dumps` prints the value; the tolerance is gone and the comparison is on the exact text. Agreement and kappa stay at two decimals (acceptance 5). | `test_every_record_number_in_the_report_is_the_exact_text_of_its_summary_value` |
| 3 numbers-outside-baseline-data | Removed or reworded every number not from `summary.json` or `labels.jsonl` (list below) | `test_every_number_in_the_report_comes_from_summary_or_labels`, `test_number_scan_flags_a_number_from_outside_the_data` |

Number scan rule: a number token is digits not preceded by a letter, digit, `#`, `.` or `-` and not followed by a letter or digit, so `I5`, `R5`, `T1`, `BM25` and `#154` are not numbers. Allow-list, removed before the scan: backticked spans (record paths, file names, commands, the SHA) unless the span is a bare number; `Phase <n>`; `Lead <n>`; the two acceptance-5 label figures. Every remaining token must equal a number in `summary.json` (numeric values, and digits inside its strings such as the `rebuild.scan` reason) or a count from `labels.jsonl` (row count, null-final count, label counts per labeller and for `final`, `final` per band, zero). Limit: a stray number that happens to equal one of those values passes (mutation N2 below). Spelled-out structural counts that define the run and the card (one run, seven records, two labellers, the eight leads, one `wrong` rating) are not scanned.

Removed or reworded numbers in `docs/knowledge-baseline.md`:
- run exit code `0` (now "completed with no probe failure");
- count of untracked files (`three`) and the dated file name; now "untracked files outside `wiki/` and `raw/`, under `.github/workflows/` and `demo/`";
- "four decimals" rounding rule; record values now exact;
- sqlite-vec version `0.1.9` and the stored dimension `0`;
- "the three model-id, template and source steps";
- `Recall@5` and `nDCG@10` headers, now the metric-name stems `recall5_<group>` and `ndcg10_<group>`;
- word 5-grams and the band edges `0.8` and `0.2`, now a pointer to R5 and R6 of `specs/tasks/T1-KBEVAL-TRACE.md`;
- sample limits `30` pages and `60` sentences, now a pointer to R8 of the trace card;
- labeller call count `9` and "four label definitions";
- "All three disagreements", "names the two", "Three ingest orders", "Ten templates";
- trust page counts "one / three / ten" and refine percentages `50, 10, 1 and 0`, now pointers to the `k` and percentage in the metric names and R9 of `specs/kb-baseline.md`;
- "1 percent" in lead 8, now `accepted_1` / `refused_0`;
- "56 sentences" and "three rows" in the last section, now "the sample sentences" and the `Rows with a null final` figure;
- "one refine call", "one owner's ... at one commit".

No statement was dropped; each was reworded to rest on a metric path or a requirement id.

### Mutation checks (applied one at a time, tests run, file restored; none committed)
| Mutation | Caught by |
|---|---|
| N1 "The run took 7 minutes." added | `test_every_number_in_the_report_comes_from_summary_or_labels` |
| N2 "It used 9 calls." added | not caught: 9 is a value in `summary.json` (stated limit) |
| N3 `contradiction.detect.recall` written as `0.2439` | exact-text test and number scan |
| N4 `linker.inject.recall` written as `0.50` | exact-text test and number scan |
| N5 kappa written as `0.8875` | acceptance-5 test and number scan |
| N6 `final_rule_errors` with `ownerRuled` checked first (the RED commit) | `test_final_rule_rejects_an_owner_ruling_that_overrides_agreed_labels` |
