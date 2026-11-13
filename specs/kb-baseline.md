---
slug: kb-baseline
title: Knowledge-layer baseline (Phase 0) measured from raw data, with no behaviour change
intent: intent/kb-baseline.md
status: accepted
created: 2026-11-13T11:10:00Z
skills_applied: [tdd]
---

# Spec: Knowledge-layer baseline (Phase 0) measured from raw data, with no behaviour change
From intent: intent/kb-baseline.md. Status: accepted. Skills applied: tdd.

No test or metric in this repository reads wiki content against its sources. Eight leads from a read of commit 0b55188 name defects in contradiction detection, Chinese retrieval, auto-linking, citation handling, claim traceability, rebuild determinism, trust and provenance. Phase 0 gives each lead a number and changes no behaviour.

## Requirements (EARS)
- R1. The command `python bench/knowledge/run.py` shall run every probe module under `bench/knowledge/probes/`, write one JSON record per probe under `_local/knowledge/` and print one summary line per probe arm, without a model call, a network request or a change to any file under the checkout's `wiki/`, `raw/` or `.data/`.
- R2. IF a probe arm cannot run because a model file or a corpus directory is absent, THEN the runner shall record that arm as `unmeasured` with a reason instead of a zero or an error.
- R3. The `contradiction` probe shall report precision and recall of `kb.ingest.contradiction.detect_contradictions` and of `_has_contradiction_signal` on a committed labelled case set, in total and per category.
- R4. The `retrieval` probe shall report recall@5 and nDCG@10 of `kb.query.engine.search_pages` for English queries, Chinese queries and Chinese queries whose relevant page is English, with the vector branch off and on, and the number of tokens `kb.query.bm25.tokenize` returns for each Chinese query.
- R5. The `linker` probe shall report precision and recall of `kb.compile.linker.inject_wikilinks` on a committed labelled case set, in total and per category.
- R6. The `citations` probe shall report, for scripted answers passed through `kb.query.engine.query_wiki`, how many citations of pages outside the prompt context and of pages that do not exist are returned in the result's `citations`.
- R7. The `trace` probe shall report, for a wiki directory and its raw directory, the share of body sentences in each of three lexical-containment bands against the page's listed sources, the number of extraction templates under `templates/` whose fields include a quote or character offsets for a claim, and a fixed sample of sentences for labelling.
- R8. The `rebuild` probe shall report, for committed sources ingested with committed extractions, the files changed by a second ingest, the page differences between three ingest orders, and whether `kb.compile.compiler.find_changed_sources` reports a change after a model id change, a template change and a source change.
- R9. The `provenance` probe shall report the `trust` value of each cited page after one `wrong` rating for 1, 3 and 10 cited pages, whether `kb.review.refiner.refine_page` accepts a body of 50, 10, 1 and 0 percent of the original length, and the share of pages whose sources all lie under `raw/captures/`.
- R10. The document `docs/knowledge-baseline.md` shall report every number of R3 to R9 from one run on the main checkout, the labels of the trace sample with the agreement rate of two labellers, and for each invariant I1 to I11 a measured value or `unmeasured` with the reason.
- R11. The change set shall leave `src/kb/`, `templates/`, `tests/`, `pyproject.toml` and `requirements.txt` unchanged.

## Design
One module per probe under `bench/knowledge/probes/`, each exporting `run(ctx)` and returning arms. The runner finds probes by listing that directory, so a probe card adds files and edits none that another card owns. A probe builds any wiki it needs in a temporary directory from files under `bench/knowledge/data/<probe>/`; the two corpus probes (`trace`, the captures arm of `provenance`) read the directories given by `--wiki` and `--raw`, which default to `demo/wiki` and `demo/raw`.

Record (one file per probe, no timestamp, so two runs on one commit give equal bytes):
`{"probe": str, "invariants": [str], "commit": 40-hex, "dirty": bool, "arms": {name: {"status": "measured" | "unmeasured", "reason": str (only when unmeasured), "cases": int, "metrics": {name: number}}}}`

Invariants. I1 to I9 are the ones the owner listed; I10 and I11 are added because leads 1 and 3 have no invariant among them.
- I1 traceable: every factual sentence of a page maps to a claim with a source path, offsets and a verbatim quote found at those offsets. Probes: `trace`, `citations`.
- I2 supported: a claim is entailed by its quote, judged by a verifier calibrated on human labels. Probe: the labels on the `trace` sample.
- I3 deterministic and idempotent: equal inputs rebuild to equal bytes, and a second ingest of a source changes nothing. Probe: `rebuild`.
- I4 order-independent: one set of sources gives one set of claims in any ingest order. Probe: `rebuild`.
- I5 retraction cascade: removing a source changes only claims that depend on it alone. No probe in Phase 0.
- I6 independent corroboration: model-written text is never the source of a confirmed belief. Probe: `provenance`.
- I7 crash-consistent: a kill at any write point leaves the state before or after the ingest. No probe in Phase 0.
- I8 cross-language: a Chinese and an English query for one concept reach the same pages. Probe: `retrieval`.
- I9 no drift: repeated refine or re-ingest leaves the claim set unchanged. Probe: the refine arm of `provenance` only.
- I10 conflict detected: two sources that state different values for one fact are flagged. Probe: `contradiction`.
- I11 link correct: an inserted link points at the page the text means. Probe: `linker`.

Definitions:
- Precision and recall: over the labelled rows of a case set, positive = the label that the function under test is meant to produce (`contradiction`, `should_link`).
- Recall@5: relevant pages in the first five results / relevant pages, averaged over queries. nDCG@10: binary gain, log2 discount.
- Lexical containment of a sentence: the share of its word 5-grams (character 8-grams when the sentence has no ASCII letters) that occur in any text source the page lists. Bands: at least 0.8, 0.2 to 0.8, below 0.2. It measures copied wording, not entailment.
- Source span: a machine-readable triple of source path, character offsets and quote attached to a sentence or claim.

## Interfaces and contracts
Frozen by the harness card: the record shape above, the `run(ctx)` probe entry, the runner's options (`--probe`, `--probes-dir`, `--out`, `--wiki`, `--raw`) and its exit codes (0 every probe returned, 1 a probe raised or a guarded directory changed, 2 usage error). No interface of `kb` changes.

## Data model and migration impact
none: every source is read-only and the output under `_local/knowledge/` is gitignored working state.

## Flagged concerns (route to policy owners)
- `wiki/` and `raw/` are untracked and may hold private text. The committed label file carries ids, offsets and hashes; sentence text stays under `_local/knowledge/` (intent, Decisions).
- The contradiction, linker and retrieval case sets are written by the implementer, a language model. Each row carries a `why` field naming the fact that makes its label true, and the reviewer reads the rows; an external labelled set (WikiContradict) is a later goal.

## Non-goals
- Any change to `kb` behaviour, prompts, templates or the `kb` CLI.
- Any fix for the eight leads, and any target for a later phase.
- Probes for I5 and I7, and the multi-round drift part of I9.
- External data sets (LLM-AggreFact, ALCE, WikiContradict, LongMemEval) and a trained verifier (MiniCheck, NLI).
- Mutation testing, flaky-test counts and git-history statistics of the existing suite.

## Acceptance
- 1. `python bench/knowledge/run.py` on the main checkout exits 0 and writes seven records, and the file listing of `wiki/`, `raw/` and `.data/` (path, size, modification time) is the same before and after. [R1]
- 2. With the embedding model absent, the vector arm of `retrieval` is `unmeasured` with a reason and the run still exits 0. [R2]
- 3. The `contradiction` record holds precision and recall for both functions and a row count per category that sums to the case count. [R3]
- 4. The `retrieval` record holds recall@5 and nDCG@10 for the three query groups and the token count per Chinese query. [R4]
- 5. The `linker` record holds precision and recall in total and per category. [R5]
- 6. The `citations` record holds injected and returned counts for in-context, out-of-context and nonexistent pages. [R6]
- 7. The `trace` record's three band counts sum to its sentence count, and the sample holds 60 sentences from 30 pages or the smaller number the corpus allows, which the record states. [R7]
- 8. The `rebuild` record holds the changed-file count of the second ingest, the differing-page counts of the order pairs and three booleans for the scan. [R8]
- 9. The `provenance` record holds a trust value for each of the 14 cited pages, four accept-or-refuse results and the captures share. [R9]
- 10. `docs/knowledge-baseline.md` carries each number with the probe and arm that produced it and a row for each of I1 to I11. [R10]
- 11. `git diff --numstat <goal base>...main -- src/kb templates tests pyproject.toml requirements.txt` is empty. [R11]
