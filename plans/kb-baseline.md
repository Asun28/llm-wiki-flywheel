---
slug: kb-baseline
title: Knowledge-layer baseline (Phase 0)
spec: specs/kb-baseline.md
size: T1
status: draft
created: 2026-11-13T11:20:00Z
---

# Plan: knowledge-layer baseline, Phase 0 (from specs/kb-baseline.md)

## 1. Goal and boundaries
The owner can rerun `python bench/knowledge/run.py` and read `docs/knowledge-baseline.md` to get a number for each of the eight leads of the intent and, for each invariant I1 to I11, a measured value or `unmeasured` with the reason.

In scope: the runner, seven probes with their case sets and tests, one CI step, the report with its label file.

Cut: every fix; probes for I5 and I7; multi-round drift (I9); external data sets; a trained verifier; mutation testing, flaky-test counts and git-history statistics.

Deferred to later goals, each opened from an intent that cites this baseline: a claim layer with quotes and offsets; a CJK tokenizer and a multilingual embedding model; link disambiguation; a citation check against the prompt context; a cache key that includes model id and prompt hash, with a stored response record; a replacement for the keyword contradiction check; a deletion guard in `refine_page`; captures excluded as confirming sources.

Success: acceptance 1 to 11 of the spec. Nothing changes under `src/kb/`, `templates/` or `tests/`, and `pyproject.toml` and `requirements.txt` stay as they are.

## 2. Minimal acceptable loop
The harness and the `contradiction` probe. That probe needs no wiki directory and no model, calls two functions on a committed case set and already answers lead 1 with a precision and a recall.

## 3. Tech stack
Python 3.12 standard library and the installed `kb` package; pytest and ruff as already pinned. No new dependency.

## 4. Directory structure
- `bench/knowledge/run.py`: the runner.
- `bench/knowledge/probes/<name>.py`: one module per probe.
- `bench/knowledge/data/<name>/`: the committed case set or fixture corpus of one probe.
- `bench/knowledge/tests/test_<name>.py`: the tests of one probe; `test_runner.py` for the runner.
- `bench/knowledge/invariants.json`, `bench/knowledge/README.md`.
- `bench/knowledge/summary.json`, `bench/knowledge/labels.jsonl`, `docs/knowledge-baseline.md`: the baseline run.
- `_local/knowledge/`: run output, gitignored.

## 4.5 Module design
- `run.py`: lists the probes, builds `ctx`, points the default paths of `kb.config` at a temporary root, guards `wiki/`, `raw/` and `.data/`, validates and writes records, prints the summary lines.
- `probes/contradiction.py`, `probes/linker.py`, `probes/retrieval.py`, `probes/citations.py`, `probes/rebuild.py`: each builds its inputs under `ctx.tmp` from `ctx.data` and calls public `kb` functions.
- `probes/trace.py`, `probes/provenance.py`: read `ctx.wiki` and `ctx.raw`; `provenance` also has two arms on temporary data.

## 5. Data model and state machine
none this version

## 6. Contracts and core interfaces
Frozen by T1-KBEVAL-HARNESS-3: the record shape, the `run(ctx)` entry with `ctx.tmp`, `ctx.data`, `ctx.wiki`, `ctx.raw`, `ctx.out` and `ctx.unmeasured(reason)`, the options `--probe`, `--probes-dir`, `--out`, `--wiki`, `--raw`, and the exit codes 0, 1 and 2 (spec, Interfaces and contracts). No interface of `kb` changes.

## Files that change
- bench/knowledge/run.py (new)
- bench/knowledge/README.md (new)
- bench/knowledge/invariants.json (new)
- bench/knowledge/tests/conftest.py (new)
- bench/knowledge/tests/test_runner.py (new)
- .github/workflows/ci.yml
- bench/knowledge/probes/contradiction.py (new)
- bench/knowledge/data/contradiction/cases.jsonl (new)
- bench/knowledge/tests/test_contradiction.py (new)
- bench/knowledge/probes/retrieval.py (new)
- bench/knowledge/data/retrieval/pages.jsonl (new)
- bench/knowledge/data/retrieval/queries.jsonl (new)
- bench/knowledge/tests/test_retrieval.py (new)
- bench/knowledge/probes/linker.py (new)
- bench/knowledge/data/linker/cases.jsonl (new)
- bench/knowledge/tests/test_linker.py (new)
- bench/knowledge/probes/citations.py (new)
- bench/knowledge/data/citations/pages.jsonl (new)
- bench/knowledge/data/citations/questions.jsonl (new)
- bench/knowledge/tests/test_citations.py (new)
- bench/knowledge/probes/trace.py (new)
- bench/knowledge/tests/test_trace.py (new)
- bench/knowledge/probes/rebuild.py (new)
- bench/knowledge/data/rebuild/sources.jsonl (new)
- bench/knowledge/data/rebuild/extractions.json (new)
- bench/knowledge/tests/test_rebuild.py (new)
- bench/knowledge/probes/provenance.py (new)
- bench/knowledge/tests/test_provenance.py (new)
- bench/knowledge/summary.json (new)
- bench/knowledge/labels.jsonl (new)
- bench/knowledge/tests/test_baseline.py (new)
- docs/knowledge-baseline.md (new)
- CHANGELOG.md
- CHANGELOG-history.md

## Order of work
1. T1-KBEVAL-HARNESS-3: the runner, the record shape, the guard, the CI step. It freezes the probe interface and runs alone. Second successor (goal revision 3): T1-KBEVAL-HARNESS stopped on a base CI breakage fixed by #146, and T1-KBEVAL-HARNESS-2 on a Linux-only test defect; it continues from that card's branch.
2. T1-KBEVAL-CONTRADICTION: lead 1. Depends on 1.
3. T1-KBEVAL-RETRIEVAL: lead 2. Depends on 1.
4. T1-KBEVAL-LINKER: lead 3. Depends on 1.
5. T1-KBEVAL-CITATIONS: lead 4. Depends on 1.
6. T1-KBEVAL-TRACE: lead 5. Depends on 1.
7. T1-KBEVAL-REBUILD: lead 6. Depends on 1.
8. T1-KBEVAL-PROVENANCE: leads 7 and 8. Depends on 1.
9. T1-KBEVAL-BASELINE: the run on the main checkout's `wiki/` and `raw/`, the labels and the report. Depends on 2 to 8.

Cards 2 to 8 each own one probe module, one data directory and one test file, share no file and declare no shared resource, so two may run at a time. Cards 1 and 9 run alone.

## 7. Task split (dependencies and parallel windows)

| Card | Priority | Output | depends_on | Parallel window | Freeze point |
|---|---|---|---|---|---|
| T1-KBEVAL-HARNESS-3 | MUST | the runner, the record shape, the directory guard, the CI step | - | - | yes |
| T1-KBEVAL-CONTRADICTION | MUST | precision and recall of contradiction detection per category | T1-KBEVAL-HARNESS-3 | W1 | - |
| T1-KBEVAL-RETRIEVAL | MUST | recall@5 and nDCG@10 for English, Chinese and cross-language queries | T1-KBEVAL-HARNESS-3 | W1 | - |
| T1-KBEVAL-LINKER | MUST | precision and recall of auto-linking per category | T1-KBEVAL-HARNESS-3 | W1 | - |
| T1-KBEVAL-CITATIONS | MUST | counts of out-of-context and nonexistent citations returned | T1-KBEVAL-HARNESS-3 | W1 | - |
| T1-KBEVAL-TRACE | MUST | lexical containment bands, source-span count, the label sample | T1-KBEVAL-HARNESS-3 | W1 | - |
| T1-KBEVAL-REBUILD | MUST | second-ingest changes, order differences, the changed-source scan | T1-KBEVAL-HARNESS-3 | W1 | - |
| T1-KBEVAL-PROVENANCE | MUST | trust change per cited page, refine acceptance, captures share | T1-KBEVAL-HARNESS-3 | W1 | - |
| T1-KBEVAL-BASELINE | MUST | the run on the real corpus, the labels and `docs/knowledge-baseline.md` | T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-LINKER, T1-KBEVAL-CITATIONS, T1-KBEVAL-TRACE, T1-KBEVAL-REBUILD, T1-KBEVAL-PROVENANCE | - | - |

## Risks
- The case sets are written by the implementer, a language model, and a set can be written toward a result. Each card fixes the categories and the minimum rows per category, each row carries a `why`, and the reviewer reads the rows.
- A `kb` function may write to a default path (`.data/`, the manifest, the vector index) even when it is given a temporary `wiki_dir`. The runner points the defaults at a temporary root and the guard fails the run when `wiki/`, `raw/` or `.data/` changes.
- The vector arm of `retrieval` needs the embedding model on disk. CI has none, so that arm is `unmeasured` there and is measured only in the baseline run.
- Lexical containment measures copied wording. A faithful paraphrase scores low and a copied sentence in the wrong context scores high; the labels on the sample are the only measure of support.
- Nine cards against the 12 hour arc: the harness, then seven probes two at a time, then the baseline. The baseline card stops with the label sheet prepared if the owner has not ruled on label disagreements by then.
- `test` is the one required check, and T1-KBEVAL-HARNESS-3 adds the `bench/knowledge/tests` step to that job, so from the harness on a failing bench test blocks the merge of every later card.
- `wiki/` and `raw/` exist only on the main checkout. Probe cards test against `demo/` and temporary fixtures; the corpus numbers come only from the baseline card.

## Proof
- Card DoDs and CI on each card.
- Arc: `python bench/knowledge/run.py --wiki wiki --raw raw` on the main checkout exits 0 and writes seven records.
- Arc: every number in `docs/knowledge-baseline.md` equals its value in `bench/knowledge/summary.json`.
- Arc: `git diff --numstat <goal base>...main -- src/kb templates tests pyproject.toml requirements.txt` is empty.

## 10. After merge
none this version (development-only target)
