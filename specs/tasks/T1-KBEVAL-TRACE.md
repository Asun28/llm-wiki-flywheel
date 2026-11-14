---
id: T1-KBEVAL-TRACE
title: "The `trace` probe reports, for a wiki and its raw directory, the lexical containment of body sentences in their listed sources, the extraction templates that define a claim quote or offsets, and a fixed sample of sentences for labelling"
status: todo
branch: T1-KBEVAL-TRACE
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-TRACE
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/trace.py
  - bench/knowledge/tests/test_trace.py
  - specs/tasks/T1-KBEVAL-TRACE.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_trace.py -q
dod_exit: 0
requirements:
  - R1. The probe shall read every `*.md` file in a subdirectory of `ctx.wiki` as a page, with the page id `<subdirectory>/<stem>` and the `source` frontmatter field as its list of refs, and shall count a file whose frontmatter does not parse in `pages_unparsed` and a page with no ref in `pages_no_source_field`.
  - R2. The probe shall resolve a ref `raw/<rest>` to `ctx.raw/<rest>` and count every ref in `refs_total` and in exactly one of `refs_text` (a file with suffix `.md`, `.txt` or `.vtt` that decodes as UTF-8), `refs_undecodable`, `refs_non_text` (another suffix), `refs_missing` (no regular file), `refs_url` (starts with `http://` or `https://`) and `refs_outside` (any other ref, or one that resolves outside `ctx.raw`), without a file-system call on a `refs_outside` or `refs_url` ref.
  - R3. The body of a page shall be its text after the frontmatter, without fenced code blocks, heading lines, table rows and the text from the line `## Evidence Trail` to the next `## ` heading or the end, and its sentences shall be the pieces between sentence ends (`.`, `!`, `?` followed by white space or the end of a line; `。`, `！`, `？` anywhere), stripped, numbered from 0 in order.
  - R4. A sentence shorter than 20 characters, or shorter than 8 when it holds no ASCII letter, shall be counted in `sentences_short` and left out of every other count.
  - R5. The containment of a sentence shall be the share of its word 5-grams (lower-cased `\w+` words), or of its character 8-grams when it holds no ASCII letter, that occur in the `refs_text` sources of its page, and a sentence too short to form one n-gram shall be counted in `sentences_short`.
  - R6. The arm `containment` shall report `cases` (the pages read) and `pages_unparsed`, `pages_no_source_field`, `pages_no_text_source`, the six `refs_` counts with `refs_total`, `sentences`, `sentences_short`, `sentences_no_text_source`, and `band_high` (containment at least 0.8), `band_mid` (at least 0.2 and below 0.8) and `band_low` (below 0.2), where the three bands sum to `sentences` minus `sentences_no_text_source`.
  - R7. The arm `templates` shall report `templates_total` (the `*.yaml` files under the checkout's `templates/`) and `templates_with_claim_span` (those in which a field name holds `quote`, `span`, `offset` or `char_`).
  - R8. The probe shall write `trace-sample.jsonl` under `ctx.out` with two sentences from each of the first 30 pages, in ascending order of the sha256 of the page id, that have at least two banded sentences, taking in each page the two with the smallest sha256 of `<page id>:<sentence index>`, one JSON object per line with `page`, `sentence_index`, `start`, `end` (character offsets in the page file), `sha256` (of the sentence text), `band`, `containment`, `sources` and `text`, and shall report `sample_pages` and `sample_sentences` in the `containment` arm.
  - R9. IF `ctx.wiki` holds no page, THEN the `containment` arm shall be `unmeasured` with the reason `no pages` and no sample file shall be written.
  - R10. The probe shall return `invariants` equal to `["I1"]`.
acceptance:
  - 1. `test_trace.py`, a temporary wiki and raw directory: a root-level `index.md` is not a page; a page with broken frontmatter is in `pages_unparsed`; a page with no `source` is in `pages_no_source_field`; the page ids are `<subdirectory>/<stem>`. [R1] [dod arm 2]
  - 2. Same file, one ref of each of the six kinds, with `Path.stat`, `Path.exists` and `open` wrapped: each ref is counted once in its kind and in `refs_total`, and no wrapped call receives the `refs_outside` or `refs_url` ref. [R2] [dod arm 2]
  - 3. Same file: a body with a fenced block, a heading, a table row and an `## Evidence Trail` section followed by another `## ` section yields exactly the expected sentence list, in English and in Chinese, with the expected indexes. [R3] [dod arm 2]
  - 4. Same file: a 19-character sentence and a 7-character Chinese sentence are in `sentences_short`; a 20-character sentence of three words is in `sentences_short` under R5; none of them is in a band. [R4] [R5] [dod arm 2]
  - 5. Same file: a sentence copied from the source has containment 1.0, a sentence sharing no 5-gram has 0.0, a sentence with 2 of 4 word 5-grams in the source has 0.5, and a Chinese sentence copied from the source has 1.0; the band counts and their sum follow R6. [R5] [R6] [dod arm 2]
  - 6. Same file, a temporary templates directory given to the probe: a template with a `quote` field is counted in `templates_with_claim_span` and one with only `key_claims` is not. [R7] [dod arm 2]
  - 7. Same file, a wiki of 32 pages with three banded sentences each: the sample holds 60 rows from the 30 pages with the smallest sha256, the two rows of each page are the ones with the smallest sha256 of `<page id>:<index>`, `start` and `end` cut the sentence out of the page file, and a second run writes a byte-equal file; a wiki of 3 such pages gives 6 rows with `sample_pages` 3. [R8] [dod arm 2]
  - 8. Same file: an empty wiki gives `unmeasured` with `no pages` and no sample file; `demo/wiki` with `demo/raw` run through the runner exits 0 with `invariants` equal to `["I1"]`. [R9] [R10] [dod arm 2]
depends_on: [T1-KBEVAL-HARNESS-3]
parallelizable_with: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-LINKER, T1-KBEVAL-CITATIONS, T1-KBEVAL-REBUILD, T1-KBEVAL-PROVENANCE]
budget: 500
forbid: [any change under src/kb/ templates/ or tests/, a write under `ctx.wiki` or `ctx.raw`, writing sentence text anywhere but `ctx.out`, a model call or network request, a new dependency such as rapidfuzz, a threshold or pass/fail judgement on a band]
non_goals: [entailment or support (the labels of T1-KBEVAL-BASELINE measure it; containment measures copied wording only), PDF and image sources (counted in `refs_non_text`, not read), fuzzy matching beyond n-gram membership, sentences inside tables and code, symbolic links under `ctx.raw` (a ref through one is read as its target and is not checked for containment in `ctx.raw` beyond the path), any fix]
hygiene: "The definitions of R3 to R5 fix the number; change one only by amending this card. `trace-sample.jsonl` holds text from the wiki that is read, so it is written only under `ctx.out`, which is gitignored by default. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-TRACE

## Deliverable
The first numbers for lead 5 of `intent/kb-baseline.md` and for invariant I1: how much of a page's wording is found in its listed sources, whether any extraction template can carry a quote or offsets, and the fixed sample that the baseline card labels.

## Why
`templates/*.yaml` define `key_claims` as plain strings and pages cite sources at file level, so no sentence of the wiki can be checked against a source by a program today. The containment bands show how many sentences a later claim layer could anchor to verbatim source text without a model, and the sample gives the only measure of support in Phase 0 once it is labelled.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_trace.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
