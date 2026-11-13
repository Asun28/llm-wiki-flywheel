---
slug: kb-baseline
title: Measure the knowledge layer of the wiki from raw data before changing any behaviour
author: asun28 (engineer)
status: accepted
created: 2026-11-13T11:00:00Z
source: human
---

# Intent: Measure the knowledge layer of the wiki from raw data before changing any behaviour
Author: asun28 (engineer). Status: accepted.

## Problem
The storage and safety layer has been through 97 review cycles (durable
renames, per-page locks, path containment, prompt fences). Nothing in the
repository measures whether the wiki content is correct: no test or metric
reads a real page against its source, and no number exists for contradiction
detection, retrieval in Chinese, auto-link precision or citation validity.

An external read of commit 0b55188 on 2026-11-13 produced eight leads:

1. `ingest/contradiction.py:_has_contradiction_signal` flags a pair only when
   exactly one side holds a negation word, so date and number conflicts pass
   and unrelated negations are flagged.
2. `query/bm25.py:tokenize` uses `\b\w[\w-]*\w\b`, which returns a run of
   Chinese text as one token; the default embedding model
   (`minishlab/potion-base-8M`) is English.
3. `compile/linker.py:_build_title_pattern` is case-insensitive with no
   disambiguation, and `\b` does not separate a Chinese title from the
   Chinese text around it.
4. `query/engine.py:1150` returns the citations extracted from the answer
   without checking that the cited page was in the prompt context.
5. `templates/*.yaml` define `key_claims` as plain strings with no quote or
   offsets; pages cite sources at file level only.
6. `compile/compiler.py` keys its manifest on the source hash and the
   template hashes; the model id, the prompt text and the backend are not in
   the key, and no page records the model that wrote it.
7. `feedback/store.py` derives trust from user ratings only.
8. `review/refiner.py:refine_page` accepts a body much shorter than the page
   it replaces, and `raw/captures/` holds model-written text that is treated
   as a raw source.

These are leads, not measurements. One was already wrong in detail when
checked against the code on 2026-11-13: the lead said one `wrong` rating is
split across the cited pages; `add_feedback_entry` adds a full `wrong` count
to every cited page. No fix for any of the eight can be shown to help or
hurt until each has a number.

## Proposed outcome
This goal is Phase 0: baseline and diagnosis, with no behaviour change. When
it is done, the owner can rerun `python bench/knowledge/run.py` and read
`docs/knowledge-baseline.md` to get:

- Precision and recall of contradiction detection on a labelled case set,
  per category (negation, both sides negated, date, number, paraphrase,
  negated paraphrase, unrelated negation).
- Recall@5 and nDCG@10 of page search for English queries, Chinese queries
  and Chinese queries whose relevant page is English, with the vector branch
  off and on.
- Precision and recall of auto-linking on a labelled case set, per category.
- How many citations of pages outside the prompt context, and of pages that
  do not exist, the query path returns.
- On the owner's local `wiki/` and `raw/`: the share of body sentences whose
  text is found in a listed source, the number of extraction templates that
  define a quote or offsets for a claim, and labels (supported, partly
  supported, unsupported, not a claim) on a fixed sample of 60 sentences
  with the agreement rate of two labellers.
- Whether a second ingest of the same sources changes any file, whether
  three ingest orders give the same pages, and whether a model id change is
  seen by the changed-source scan.
- The trust value of each cited page after one `wrong` rating, the shortest
  replacement body `refine_page` accepts, and the share of pages whose
  sources all lie under `raw/captures/`.
- For each invariant I1 to I11 of `specs/kb-baseline.md`: a measured value,
  or `unmeasured` with the reason.

Fixes (a claim layer with quotes and offsets, a CJK tokenizer, link
disambiguation, a citation check, a wider cache key, a replacement for the
keyword contradiction check) are later goals. Their targets are set from
this baseline and approved by the owner before any of them starts.

## Affected users and systems
- The repository owner, the only user and the only reviewer of wiki content.
- New dev-only files: `bench/knowledge/` (runner, probes, case sets, tests)
  and `docs/knowledge-baseline.md`.
- One CI change: `.github/workflows/ci.yml` also lints `bench/` and runs
  `bench/knowledge/tests`.
- Read only: `src/kb/`, `templates/`, `demo/`, and on the main checkout the
  untracked `wiki/` (183 markdown files) and `raw/` (31 markdown files, one
  `.vtt`, one `.png`).
- No change under `src/kb/`, `templates/` or `tests/`, and none to
  `pyproject.toml` or `requirements.txt`.

## Constraints
- No behaviour change, no new dependency, no new command in the `kb` CLI.
- No probe calls a model or the network. An arm that needs a model file
  that is not on disk reports `unmeasured` with the reason.
- No probe writes under the checkout's `wiki/`, `raw/` or `.data/`.
- Measurement code is dev-only and stays out of the published package.
- `tests/` is not touched, so the test counts that `scripts/verify_docs.py`
  checks stay as they are.
- Paper and vendor effect sizes (MiniCheck, ALCE, WikiContradict, HippoRAG,
  OpenWiki) and the eight leads above are leads, never evidence.
- Known gaps on 2026-11-13, to be reported, not hidden:
  - I5 (removing a source changes only the claims that depend on it alone)
    and I7 (a kill at any write point leaves the state before or after the
    ingest) have no probe in Phase 0.
  - I9 (no drift over repeated refine or re-ingest) needs model calls; Phase
    0 measures only whether `refine_page` accepts a large deletion.
  - Whether a cited page supports the sentence that cites it needs labels on
    real answers; Phase 0 measures only context membership.
  - `wiki/` and `raw/` are untracked, so the corpus numbers can be rerun
    only on the owner's machine.

## Decisions (owner, 2026-11-14)
The owner took the recommended answer to each of the three open questions.
- Corpus text is not committed. `bench/knowledge/labels.jsonl` carries page
  id, sentence index, offsets, a sha256 of the sentence and the labels; the
  sentence and source text stay under `_local/knowledge/`.
- Labels follow the rule of `intent/reliability-baseline.md` in the AIDLC
  repository: Claude labels, a model of another vendor labels blind from the
  same sentence and sources, the owner rules only on disagreements. Budget:
  20 USD of model spend for the goal.
- `aidlc.config.json`: `shipPath: github`,
  `repository: Asun28/llm-wiki-flywheel`, required check `test` (the one job
  of `ci.yml`), and the `formalReview` block of the AIDLC repository (R3 by
  `codex exec -m gpt-6-astra`, fallback `claude -p --model claude-opus-5-5`).
  Its effort escalation paths name that repository's `src/core/**`,
  `src/coordination/**` and `src/state/**`; here they are `src/kb/**`.

## Open questions
- (none)
