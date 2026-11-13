---
id: T1-KBEVAL-RETRIEVAL
title: "The `retrieval` probe reports recall@5 and nDCG@10 of `search_pages` for English, Chinese and Chinese-to-English queries with the vector branch off and on, and the token count of `tokenize` per Chinese query"
status: todo
branch: T1-KBEVAL-RETRIEVAL
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-RETRIEVAL
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/retrieval.py
  - bench/knowledge/data/retrieval/pages.jsonl
  - bench/knowledge/data/retrieval/queries.jsonl
  - bench/knowledge/tests/test_retrieval.py
  - specs/tasks/T1-KBEVAL-RETRIEVAL.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_retrieval.py -q
dod_exit: 0
requirements:
  - R1. `pages.jsonl` shall hold one JSON object per line with `id` (unique, `concepts/<slug>`), `title`, `lang` (`en` or `zh`), `role` (`target` or `distractor`) and `body`, with at least 8 English target pages, at least 8 Chinese target pages whose title and body are written in Chinese characters, and at least 8 distractor pages, half of them Chinese.
  - R2. `queries.jsonl` shall hold one JSON object per line with `id` (unique), `group`, `query`, `relevant` (a non-empty list of target page ids) and `why`, with at least 8 rows in each group. `en`, an English query of 2 to 6 words, each of which occurs in the body of its English relevant page. `zh`, a query of 2 to 8 Chinese characters that occurs verbatim in the body of its Chinese relevant page. `zh-to-en`, a query in Chinese characters that translates an `en` row's query and has that row's `relevant`.
  - R3. IF a line of either file is not a JSON object, lacks a field, repeats an `id`, names a `relevant` id that is not a target page, or breaks the rule of its `lang`, `role` or `group`, THEN the probe shall raise `ValueError` naming the file and the line number.
  - R4. The probe shall write every page as a wiki page file under `ctx.tmp` (frontmatter of the template in `CLAUDE.md`, `type: concept`) and call `kb.query.engine.search_pages(query, wiki_dir, 10)` once per query and arm.
  - R5. The arm `bm25` shall run its calls with `KB_DISABLE_VECTORS=1` and restore the previous value of that variable afterwards.
  - R6. The arm `hybrid` shall run with `KB_DISABLE_VECTORS` unset and `HF_HUB_OFFLINE=1`, after building the vector index of the temporary wiki, and IF the embedding model cannot be loaded, the index cannot be built, or the vector branch returns no hit for every query, THEN the arm shall be `unmeasured` with the cause as reason.
  - R7. Each measured search arm shall report `cases` (the query count) and, for each group, `queries_<group>`, `recall5_<group>`, `ndcg10_<group>` and `zero_result_<group>`, with recall@5 and nDCG@10 as defined in `specs/kb-baseline.md`.
  - R8. The arm `tokenize` shall report, for each `zh` and `zh-to-en` row, `tokens_<id>` (the length of `kb.query.bm25.tokenize(query)`), and `zh_queries`, `zh_zero_token`, `zh_single_token` and `zh_mean_tokens` over those rows.
  - R9. The probe shall return `invariants` equal to `["I8"]`.
acceptance:
  - 1. `test_retrieval.py`: the committed files load under R1 to R3 with the minimum counts, and each `zh` query is a substring of its relevant page's body. [R1] [R2] [dod arm 2]
  - 2. Same file, one test per cause of R3 for each file: `ValueError` whose message holds the file name and the line number. [R3] [dod arm 2]
  - 3. Same file, `search_pages` replaced by a stub with fixed result lists for three queries, one of them empty: `recall5`, `ndcg10` (binary gain, log2 discount) and `zero_result` equal hand-computed values. [R7] [dod arm 2]
  - 4. Same file: the stub sees `KB_DISABLE_VECTORS` equal to `1` during the `bm25` arm, and the variable holds its earlier value, or is absent, after it. [R5] [dod arm 2]
  - 5. Same file, one test per cause (model load raises, index build raises, the vector branch returns no hit): the `hybrid` arm is `unmeasured` with a reason that names the cause, and `HF_HUB_OFFLINE` was `1` while it ran. [R6] [dod arm 2]
  - 6. Same file, the committed set: the `tokenize` arm holds one `tokens_<id>` per Chinese row, and `zh_queries`, `zh_zero_token`, `zh_single_token` and `zh_mean_tokens` equal the values recomputed from them. [R8] [dod arm 2]
  - 7. Same file, the committed set run through the runner with the real `search_pages`: exit 0, `bm25` `measured` with `cases` equal to the query count, `hybrid` either `measured` or `unmeasured` with a reason, `invariants` equal to `["I8"]`. [R4] [R9] [dod arm 2]
  - 8. Each row's `why` names the page text that makes the page relevant, and no distractor page answers a query (reviewer-verified against the diff). [R1] [R2]
depends_on: [T1-KBEVAL-HARNESS]
parallelizable_with: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-LINKER, T1-KBEVAL-CITATIONS, T1-KBEVAL-TRACE, T1-KBEVAL-REBUILD, T1-KBEVAL-PROVENANCE]
budget: 700
forbid: [any change under src/kb/ templates/ or tests/, a download of the embedding model inside the probe or its tests, a model call, a threshold or pass/fail judgement on a metric, changing a query or a page because of what `search_pages` returned for it]
non_goals: [another embedding model or tokenizer (later goals), an `en-to-zh` group (not in the spec), queries that need reasoning across pages, the effect of the graph or PageRank on ranking, timing of a search]
hygiene: "The `zh` group is a lower bound: the query string is in the page verbatim, so any tokenizer that splits Chinese can match it. Write both files before the first run. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-RETRIEVAL

## Deliverable
The first number for lead 2 of `intent/kb-baseline.md` and for invariant I8: what share of Chinese queries reach their page, next to the same figure for English.

## Why
`kb.query.bm25.tokenize` matches `\b\w[\w-]*\w\b`, which the lead says returns a run of Chinese text as one token, and the default embedding model is English. The `tokenize` arm shows the token counts, the `bm25` arm shows what that does to recall, and the `hybrid` arm shows whether the vector branch makes up for it when the model is on disk.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_retrieval.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
