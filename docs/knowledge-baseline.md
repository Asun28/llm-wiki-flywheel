# Knowledge-layer baseline (Phase 0)

This report gives the Phase 0 numbers of the knowledge bench (`bench/knowledge/`) from one run on the owner's `wiki/` and `raw/`. It states measurements only. It sets no target and makes no proposal for a later phase. Intent: `intent/kb-baseline.md`; spec and invariants: `specs/kb-baseline.md`; card: `specs/tasks/T1-KBEVAL-BASELINE.md`.

## Method

- One run of `python bench/knowledge/run.py --wiki wiki --raw raw --out _local/knowledge` on the main checkout, with the project `.venv` first on `PATH` and `HF_HUB_OFFLINE=1` set so the embedding model could not be downloaded. The run exited 0 and printed no `guarded directory changed:` line. No second run was made.
- Run commit: `82ee29f3598308572d58f4b736e8140080c72f54` (`run.commit` in `bench/knowledge/summary.json`).
- Dirty state: `run.dirty` = true. The working tree held three untracked files outside `wiki/` and `raw/`: `.github/workflows/security-scanners.yml`, `demo/2026-05-22.md` and `demo/Untitled.canvas`. No tracked file was modified. `wiki/` and `raw/` are gitignored and are not part of the dirty check.
- `bench/knowledge/summary.json` holds the seven records of that run, unedited, under `records`, keyed by probe. It was written by a script from the record files; it is not edited by hand.
- Each number taken from a record is written as `` `<probe>.<arm>.<metric>` = <value> ``. Values with more than four decimals are written to four decimals. An arm is named as `` `<probe>.<arm>` ``.
- The labels of the trace sample are in `bench/knowledge/labels.jsonl`, one row per sample sentence, with page id, sentence index, character offsets, the sha256 of the sentence and the labels. No sentence text or source text is committed; it stays under the gitignored `_local/knowledge/`.

## Corpus and gaps

- Corpus counts at the run: `run.wiki_md_files` = 183 markdown files under `wiki/`, of which `run.wiki_page_files` = 175 are pages in a subdirectory (the files the corpus probes read; the rest are root files such as `index.md` and `log.md`). `run.raw_files` = 43 files under `raw/`, a count that includes empty placeholder files such as `.gitkeep`.
- `wiki/` and `raw/` are untracked. The corpus numbers (the `trace` record and the `provenance.captures` arm) can be rerun only on the owner's machine. The other probes run on committed case sets or on temporary data and can be rerun anywhere.
- Unmeasured arms of this run:
  - `retrieval.hybrid` unmeasured: vector branch returned no hit for any query. The embedding model was on disk and the index was built. With sqlite-vec 0.1.9, `PRAGMA table_info` reports an empty type for the `embedding` column, so the stored dimension reads as 0 and every vector query returns no hit (issue #154). The vector branch and the English-only embedding model therefore have no number.
  - `rebuild.scan` unmeasured: listed_clean=6: find_changed_sources listed 6 source(s) with nothing changed since the ingest. `ingest_source` writes no `_template` keys to the manifest, so the changed-source scan reports every source as changed before any input changes, and the three model-id, template and source steps were not run.
- Invariants I5 (retraction cascade) and I7 (crash consistency) have no probe in Phase 0.
- Known measurement limits, from the probe cards:
  - The trace probe does not recognise HTML blocks, so text inside an HTML block is counted as prose (issue #157).
  - The runner accepts an `--out` directory inside `--wiki` or `--raw` (issue #148). This run used `_local/knowledge`, outside both.
  - The trace sentence rule is the literal rule of the trace card's R3: a `.` followed by white space ends a sentence, so an ordered-list marker such as `1.` becomes its own short sentence, and list items without end punctuation join into one long sentence. Several rows of the label sample are whole link lists or several bullet items for this reason.
  - The citations probe passes a scripted model answer through the real query path. It measures what the query path does with the citations it is given, not what a model writes.
  - The provenance trust and refine arms run on temporary data under the probe's own directory, not on the owner's feedback store or pages.

## Invariants

One row per invariant of `bench/knowledge/invariants.json`.

| Id | Statement (short) | Metrics | Status |
|---|---|---|---|
| I1 | Traceable to a source span | `trace.templates.templates_with_claim_span` = 1 of `trace.templates.templates_total` = 11; `trace.containment.band_high` = 71 of `trace.containment.sentences` = 318; `citations.scripted.returned_out-of-context` = 12; `citations.scripted.returned_nonexistent` = 12 | measured |
| I2 | Supported, judged on human-calibrated labels | Labels section: two-labeller labels on the trace sample | measured (labels only, no verifier) |
| I3 | Deterministic and idempotent | `rebuild.idempotence.page_files_changed_by_second` = 0; `rebuild.idempotence.files_changed_by_second` = 2 | measured |
| I4 | Order-independent | `rebuild.order.pages_differing_bytes_reverse` = 9; `rebuild.order.pages_differing_bytes_hashed` = 9; `rebuild.order.page_set_equal_reverse` = 1 | measured |
| I5 | Retraction cascade | none | unmeasured: no probe in Phase 0 |
| I6 | Independent corroboration | `provenance.captures.pages_all_capture_sources` = 0; `provenance.captures.confirmed_all_capture` = 0; `provenance.captures.stated_all_capture` = 0 | measured |
| I7 | Crash-consistent | none | unmeasured: no probe in Phase 0 |
| I8 | Cross-language | `retrieval.bm25.recall5_zh-to-en` = 0.0; `retrieval.bm25.recall5_en` = 1.0; `retrieval.hybrid` unmeasured | measured for the BM25 arm only |
| I9 | No drift | `provenance.refine.accepted_1` = 1; `provenance.refine.refused_0` = 1 | measured for refine acceptance only; multi-round drift needs model calls |
| I10 | Conflict detected | `contradiction.detect.precision` = 0.3125; `contradiction.detect.recall` = 0.2439 | measured |
| I11 | Link correct | `linker.inject.precision` = 0.3333; `linker.inject.recall` = 0.5 | measured |

## Contradiction detection

Probe `contradiction`, committed labelled case set (row counts per category below). Both arms gave the same counts.

- `kb.ingest.contradiction.detect_contradictions`: `contradiction.detect.tp` = 10, `contradiction.detect.fp` = 22, `contradiction.detect.fn` = 31, `contradiction.detect.tn` = 10, `contradiction.detect.precision` = 0.3125, `contradiction.detect.recall` = 0.2439.
- `_has_contradiction_signal`: `contradiction.signal.tp` = 10, `contradiction.signal.fp` = 22, `contradiction.signal.fn` = 31, `contradiction.signal.tn` = 10, `contradiction.signal.precision` = 0.3125, `contradiction.signal.recall` = 0.2439.

Flagged rows per category (detect arm):

| Category | Flagged | Rows |
|---|---|---|
| negation | `contradiction.detect.flagged_negation` = 10 | `contradiction.detect.rows_negation` = 11 |
| both-negated | `contradiction.detect.flagged_both-negated` = 0 | `contradiction.detect.rows_both-negated` = 10 |
| date | `contradiction.detect.flagged_date` = 0 | `contradiction.detect.rows_date` = 10 |
| number | `contradiction.detect.flagged_number` = 0 | `contradiction.detect.rows_number` = 10 |
| paraphrase | `contradiction.detect.flagged_paraphrase` = 0 | `contradiction.detect.rows_paraphrase` = 10 |
| negated-paraphrase | `contradiction.detect.flagged_negated-paraphrase` = 11 | `contradiction.detect.rows_negated-paraphrase` = 11 |
| unrelated-negation | `contradiction.detect.flagged_unrelated-negation` = 11 | `contradiction.detect.rows_unrelated-negation` = 11 |

## Retrieval

Probe `retrieval`, committed set of pages and queries, `kb.query.engine.search_pages` on a temporary wiki.

| Group | Queries | Recall@5 | nDCG@10 | Queries with no result |
|---|---|---|---|---|
| en | `retrieval.bm25.queries_en` = 8 | `retrieval.bm25.recall5_en` = 1.0 | `retrieval.bm25.ndcg10_en` = 1.0 | `retrieval.bm25.zero_result_en` = 0 |
| zh | `retrieval.bm25.queries_zh` = 8 | `retrieval.bm25.recall5_zh` = 0.0 | `retrieval.bm25.ndcg10_zh` = 0.0 | `retrieval.bm25.zero_result_zh` = 8 |
| zh-to-en | `retrieval.bm25.queries_zh-to-en` = 8 | `retrieval.bm25.recall5_zh-to-en` = 0.0 | `retrieval.bm25.ndcg10_zh-to-en` = 0.0 | `retrieval.bm25.zero_result_zh-to-en` = 8 |

- Tokenizer: of `retrieval.tokenize.zh_queries` = 16 Chinese queries, `retrieval.tokenize.zh_single_token` = 16 give one token from `kb.query.bm25.tokenize` and `retrieval.tokenize.zh_zero_token` = 0 give none; `retrieval.tokenize.zh_mean_tokens` = 1.0.
- `retrieval.hybrid` unmeasured: vector branch returned no hit for any query. See Corpus and gaps.

## Auto-links

Probe `linker`, committed labelled case set (row counts per category below), `kb.compile.linker.inject_wikilinks` on a temporary wiki.

- Totals: `linker.inject.tp` = 12, `linker.inject.fp` = 24, `linker.inject.fn` = 12, `linker.inject.tn` = 24, `linker.inject.precision` = 0.3333, `linker.inject.recall` = 0.5.

| Category | Linked | Rows |
|---|---|---|
| proper-mention (link expected) | `linker.inject.linked_proper-mention` = 12 | `linker.inject.rows_proper-mention` = 12 |
| cjk-in-cjk (link expected) | `linker.inject.linked_cjk-in-cjk` = 0 | `linker.inject.rows_cjk-in-cjk` = 12 |
| common-word (no link expected) | `linker.inject.linked_common-word` = 12 | `linker.inject.rows_common-word` = 12 |
| case-variant (no link expected) | `linker.inject.linked_case-variant` = 12 | `linker.inject.rows_case-variant` = 12 |
| inside-code (no link expected) | `linker.inject.linked_inside-code` = 0 | `linker.inject.rows_inside-code` = 12 |
| already-linked (no link expected) | `linker.inject.linked_already-linked` = 0 | `linker.inject.rows_already-linked` = 12 |

## Citations

Probe `citations`, committed questions, scripted answers passed through `kb.query.engine.query_wiki`.

| Cited page class | Injected into the answer | Returned in `citations` |
|---|---|---|
| in the prompt context | `citations.scripted.injected_in-context` = 6 | `citations.scripted.returned_in-context` = 6 |
| outside the prompt context | `citations.scripted.injected_out-of-context` = 12 | `citations.scripted.returned_out-of-context` = 12 |
| page that does not exist | `citations.scripted.injected_nonexistent` = 12 | `citations.scripted.returned_nonexistent` = 12 |
| path traversal | `citations.scripted.injected_traversal` = 6 | `citations.scripted.returned_traversal` = 0 |

`citations.scripted.citation_keys_uniform` = 1: every returned citation has the same keys.

## Traceability

Probe `trace` on the owner's `wiki/` and `raw/`.

- Pages: `trace.containment.pages_unparsed` = 0, `trace.containment.pages_no_source_field` = 1, `trace.containment.pages_no_text_source` = 8.
- Source refs: `trace.containment.refs_total` = 180, of which `trace.containment.refs_text` = 173 text files, `trace.containment.refs_missing` = 3 with no file, `trace.containment.refs_outside` = 4 outside `raw/`, `trace.containment.refs_non_text` = 0, `trace.containment.refs_undecodable` = 0, `trace.containment.refs_url` = 0.
- Sentences: `trace.containment.sentences` = 318 body sentences long enough to measure, plus `trace.containment.sentences_short` = 12 short ones counted apart. `trace.containment.sentences_no_text_source` = 1 sentence is on a page with no text source.
- Lexical containment bands (share of word 5-grams found in a listed source; copied wording, not entailment): `trace.containment.band_high` = 71 at 0.8 or more, `trace.containment.band_mid` = 84 from 0.2 to below 0.8, `trace.containment.band_low` = 162 below 0.2.
- Templates: `trace.templates.templates_with_claim_span` = 1 of `trace.templates.templates_total` = 11 extraction templates has a field for a quote or offsets. The trace card names it: `book.yaml`, field `quotes`.
- Label sample: `trace.containment.sample_sentences` = 56 sentences from `trace.containment.sample_pages` = 28 pages. The corpus has fewer than 30 pages with two banded sentences, so the sample is smaller than the 60 the spec allows for.

## Labels

Each row of `bench/knowledge/labels.jsonl` carries two labels from the closed set `supported`, `partly-supported`, `unsupported`, `not-a-claim`:

- labelA: Claude (the implementer of this card), after reading the sentence and the text of the page's listed sources.
- labelB: `gpt-6-astra` through `codex exec --sandbox read-only`, given only the sentence, the text of the page's listed sources and the four label definitions, one call per distinct source list (9 calls), in an empty working directory. It was not shown labelA. The prompts and raw outputs are kept under `_local/knowledge/labelB/`.
- `final` is the shared label where the two agree and null otherwise. No row has an owner ruling yet.

Figures over all rows of `labels.jsonl` (n = 56):

- Raw agreement rate: 0.95
- Cohen's kappa: 0.89
- Rows with a null final: 3

Label counts:

| Label | labelA | labelB | final |
|---|---|---|---|
| supported | 38 | 37 | 36 |
| partly-supported | 3 | 4 | 2 |
| unsupported | 0 | 0 | 0 |
| not-a-claim | 15 | 15 | 15 |
| null | | | 3 |

`final` by containment band:

| Band | supported | partly-supported | not-a-claim | null |
|---|---|---|---|---|
| high | 13 | 0 | 0 | 0 |
| mid | 14 | 0 | 4 | 0 |
| low | 9 | 2 | 11 | 3 |

All three disagreements are between `supported` and `partly-supported`. No sentence was labelled `unsupported` by either labeller. Every `not-a-claim` row is a link list or a line that names the page's source file.

## Rebuild

Probe `rebuild`, committed sources ingested with committed extractions on temporary wikis.

- Second ingest of the same sources: `rebuild.idempotence.files_after_first` = 17 files after the first pass; `rebuild.idempotence.files_changed_by_second` = 2 files changed by the second, of which `rebuild.idempotence.page_files_changed_by_second` = 0 are pages (the probe card names the two as the root files `contradictions.md` and `log.md`).
- Three ingest orders (path order against reverse and against sha256 order): `rebuild.order.page_set_equal_reverse` = 1 and `rebuild.order.page_set_equal_hashed` = 1 (same page set); `rebuild.order.pages_differing_bytes_reverse` = 9 and `rebuild.order.pages_differing_bytes_hashed` = 9 pages differ in bytes, and `rebuild.order.pages_differing_lines_reverse` = 9 and `rebuild.order.pages_differing_lines_hashed` = 9 differ in their set of lines.
- `rebuild.scan` unmeasured: listed_clean=6: find_changed_sources listed 6 source(s) with nothing changed since the ingest. See Corpus and gaps.

## Provenance

Probe `provenance`.

- Trust after one `wrong` rating, on temporary feedback stores: with one cited page `provenance.trust.trust_k1_p1` = 0.25; with three, `provenance.trust.trust_k3_p1` = 0.25, `provenance.trust.trust_k3_p2` = 0.25, `provenance.trust.trust_k3_p3` = 0.25; with ten, `provenance.trust.trust_k10_p1` = 0.25 and `provenance.trust.trust_k10_p10` = 0.25, and every other `trust_k10_` value is the same in the record. Each cited page records the full count: `provenance.trust.wrong_k1_p1` = 1, `provenance.trust.wrong_k3_p3` = 1, `provenance.trust.wrong_k10_p10` = 1.
- `refine_page` with a replacement body of 50, 10, 1 and 0 percent of the original length: `provenance.refine.accepted_50` = 1, `provenance.refine.accepted_10` = 1, `provenance.refine.accepted_1` = 1, `provenance.refine.accepted_0` = 0, `provenance.refine.refused_0` = 1.
- Captures on the owner's wiki: `provenance.captures.pages_with_sources` = 174 pages with sources, `provenance.captures.refs_total` = 180 refs, `provenance.captures.refs_captures` = 0 under `raw/captures/`, `provenance.captures.pages_any_capture_source` = 0, `provenance.captures.pages_all_capture_sources` = 0.

## Leads

The eight leads of `intent/kb-baseline.md`, with the metrics that bear on each.

### Lead 1: contradiction check fires on exactly one negated side
Metrics: `contradiction.detect.flagged_date` = 0, `contradiction.detect.flagged_number` = 0, `contradiction.detect.flagged_both-negated` = 0, `contradiction.detect.flagged_unrelated-negation` = 11 of `contradiction.detect.rows_unrelated-negation` = 11, `contradiction.detect.recall` = 0.2439.
Date and number conflicts are never flagged, pairs where both sides are negated are never flagged, and every unrelated negation is flagged.
Verdict: confirmed

### Lead 2: Chinese text is one BM25 token; the embedding model is English
Metrics: `retrieval.tokenize.zh_single_token` = 16 of `retrieval.tokenize.zh_queries` = 16, `retrieval.bm25.recall5_zh` = 0.0, `retrieval.bm25.zero_result_zh` = 8, `retrieval.bm25.recall5_zh-to-en` = 0.0; `retrieval.hybrid` unmeasured.
The tokenizer half holds: every Chinese query is one token and no Chinese query finds its page. The embedding half has no number, because the vector branch returned no hit; the verdict covers the tokenizer half only.
Verdict: confirmed

### Lead 3: linker is case-insensitive with no disambiguation, and misses Chinese titles in Chinese text
Metrics: `linker.inject.linked_case-variant` = 12 of `linker.inject.rows_case-variant` = 12, `linker.inject.linked_common-word` = 12 of `linker.inject.rows_common-word` = 12, `linker.inject.linked_cjk-in-cjk` = 0 of `linker.inject.rows_cjk-in-cjk` = 12, `linker.inject.precision` = 0.3333.
Verdict: confirmed

### Lead 4: citations are returned without a context check
Metrics: `citations.scripted.returned_out-of-context` = 12 of `citations.scripted.injected_out-of-context` = 12, `citations.scripted.returned_nonexistent` = 12 of `citations.scripted.injected_nonexistent` = 12, `citations.scripted.returned_traversal` = 0.
Every out-of-context and nonexistent citation in the scripted answer is returned; path-traversal citations are not.
Verdict: confirmed

### Lead 5: templates carry no quote or offsets; pages cite at file level only
Metrics: `trace.templates.templates_with_claim_span` = 1 of `trace.templates.templates_total` = 11; `trace.containment.refs_total` = 180 refs, all file paths or out-of-tree paths (`trace.containment.refs_url` = 0).
Ten templates have no quote or offset field. The one exception is the `quotes` field of `book.yaml` ("Notable quotes with page numbers"), a list of quotes that is not attached to a key claim. No source ref names a span.
Verdict: confirmed

### Lead 6: the compile manifest key leaves out model id, prompt and backend
Metrics: `rebuild.scan` unmeasured (listed_clean=6), so the model-id step did not run. `rebuild.idempotence.page_files_changed_by_second` = 0 and `rebuild.order.pages_differing_bytes_reverse` = 9 bear on rebuild determinism, not on the manifest key.
Verdict: not decided

### Lead 7: trust comes from user ratings only
Metrics: `provenance.trust.trust_k1_p1` = 0.25, `provenance.trust.trust_k10_p10` = 0.25, `provenance.trust.wrong_k10_p10` = 1.
One `wrong` rating gives each cited page the same trust whether one or ten pages are cited, so the rating is not split. The probe varies no input other than ratings, so whether anything else enters the trust value is not measured.
Verdict: not decided

### Lead 8: refine accepts a much shorter body; captures are treated as raw sources
Metrics: `provenance.refine.accepted_1` = 1, `provenance.refine.refused_0` = 1; `provenance.captures.refs_captures` = 0, `provenance.captures.pages_all_capture_sources` = 0.
`refine_page` accepts a body of 1 percent of the original and refuses only an empty one. No page of the owner's wiki cites `raw/captures/`, so the captures half has no case in this corpus; the verdict covers the refine half.
Verdict: confirmed

## What these numbers do not show

- Support. The containment bands measure copied wording, not whether a source supports a sentence. The labels are from two models, not from the owner, on 56 sentences of one corpus; three rows have no `final` until the owner rules. No verifier was calibrated, so I2 has labels and no measured verifier accuracy.
- Correctness of query answers. The citations probe uses a scripted answer, so it shows how the query path treats citations, not how often a model cites a page outside its context or whether a cited page supports the sentence that cites it.
- The vector branch. `retrieval.hybrid` is unmeasured (issue #154), so nothing here says how the embedding model handles Chinese or cross-language queries.
- Cache-key coverage. `rebuild.scan` is unmeasured because `ingest_source` writes no `_template` keys, so nothing here says whether a model-id, template or source change is seen by the changed-source scan.
- Real feedback and refine history. The trust and refine arms run on temporary data; they show what the functions do with one input, not the state of the owner's feedback store or pages.
- Drift over repeated runs (I9 beyond one refine call), retraction cascade (I5) and crash consistency (I7).
- Sentence boundaries. The trace sentence rule is the trace card's literal rule: list markers become short sentences, unpunctuated list items join into one sentence, and HTML blocks are read as prose (issue #157). The sentence and band counts depend on that rule.
- Generality. The case sets for contradiction, retrieval and linking were written by a language model with a `why` per row; they are not an external labelled set. The corpus numbers come from one owner's `wiki/` and `raw/` at one commit; the runner also accepts an `--out` inside `--wiki` or `--raw` (issue #148), which this run did not use.
