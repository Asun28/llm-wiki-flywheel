---
id: T1-KBEVAL-RETRIEVAL
title: "The `retrieval` probe reports recall@5 and nDCG@10 of `search_pages` for English, Chinese and Chinese-to-English queries with the vector branch off and on, and the token count of `tokenize` per Chinese query"
status: merged
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
depends_on: [T1-KBEVAL-HARNESS-3]
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

## Attempt evidence
Attempt 1.
- First RED, commit `4d5432a`: 5 failed, 27 errors, every one a `FileNotFoundError` for `probes/retrieval.py`, `data/retrieval/pages.jsonl` or `data/retrieval/queries.jsonl`. No assertion ran, so this RED is not behavioural.
- Behavioural RED, commit `879ca12`: `probes/retrieval.py` is an importable stub whose `run(ctx)` returns `invariants: ["I8"]` and the arms `bm25`, `tokenize` and `hybrid`, each `measured` with `cases: 0` and `metrics: {}`. It reads no data file, writes no wiki and calls neither `search_pages` nor `tokenize`. The same commit adds the tests for the hub offline flag, the page-id form and an unknown lang. Result: 34 failed, 3 passed, 0 errors. Of the 34 failures, 22 are `Failed: DID NOT RAISE` from `pytest.raises` (21 `ValueError`, 1 `ArmStopped`) and 12 are `AssertionError`; none is an import, file, fixture, `KeyError` or `TypeError` error. The 3 passing tests check the committed data files and do not call the probe.
- GREEN: the next commit restores the full probe from `7ea5010` (`git checkout 7ea5010 -- bench/knowledge/probes/retrieval.py`); 37 passed.

Attempt 2 (repair of the R3 block on `390551c`, findings F1 to F4).
- RED, commit `3e1a2d0`: against the probe of `390551c`, 5 failed and 38 passed; all 5 failures are `Failed: DID NOT RAISE <class 'ValueError'>` from `test_a_query_that_breaks_its_group_rule_raises_with_file_and_line` (F1 split en words, F2 zh query missing from one body, F3 numbers only, punctuation only, a number word).
- F4: the tokenize tests now compute `len(kb.query.bm25.tokenize(query))` themselves for each zh and zh-to-en row and compare every `tokens_<id>` and the four aggregates with those values. Mutation check, not committed: replacing the count in `tokenize_arm` with the constant 0 fails both `test_tokenize_arm_counts_tokens_per_chinese_row` (19 of 20 metrics differ) and `test_tokenize_arm_counts_a_one_character_query_as_zero_tokens` (5 of 7); the constant 1 passes the committed-set test, because every committed Chinese query is one token, and fails the one-character test (4 of 7). The probe was restored with `git checkout` after each mutation.
- GREEN: en words must match `[A-Za-z]+(?:['-][A-Za-z]+)*` and be separated by single spaces, each en word must occur in every relevant body, and a zh query must occur verbatim in every relevant body. 43 passed. The committed `pages.jsonl` and `queries.jsonl` load under the stricter rules unchanged; no data row changed, and the runner numbers are the same as in attempt 1.
- Other fields with a form in R2 or R3, checked and left as they were: page ids use `fullmatch` on `concepts/[a-z0-9]+(?:-[a-z0-9]+)*`; lang and role must equal one of their two values; zh and zh-to-en queries use `fullmatch` on Han characters only; R2 names no form for a query id.

| Item | Proving test or command | Result |
|---|---|---|
| 1 | `test_committed_pages_meet_the_minimum_counts_and_language_rules`, `test_committed_queries_meet_the_minimum_counts_and_group_rules`, `test_each_zh_query_is_a_substring_of_its_relevant_page_body` | pass |
| 2 | `test_a_bad_pages_line_raises_with_file_and_line` (8 cases), `test_a_bad_queries_line_raises_with_file_and_line` (12 cases), `test_a_query_that_breaks_its_group_rule_raises_with_file_and_line` (5 cases), `test_a_line_that_is_not_utf8_raises_with_file_and_line` | pass |
| 3 | `test_search_arms_report_recall_ndcg_and_zero_results` (hand values: 1/log2(3), (1 + 1/log2(7)) / (1 + 1/log2(3)), an empty list) | pass |
| 4 | `test_bm25_arm_sets_disable_vectors_and_restores_it[0]`, `[None]` | pass |
| 5 | `test_hybrid_arm_is_unmeasured_with_the_cause` (model load raises, index build raises, index build returns False, no vector hit), `test_hybrid_arm_makes_imported_hub_offline_and_restores_it[returns]`, `[raises]` | pass |
| 6 | `test_tokenize_arm_counts_tokens_per_chinese_row` (committed set, through the runner), `test_tokenize_arm_counts_a_one_character_query_as_zero_tokens`; expected counts from `kb.query.bm25.tokenize` in the test | pass |
| 7 | `test_committed_set_runs_through_the_runner`, `test_each_query_is_searched_once_per_arm_in_a_wiki_under_tmp`, `test_pages_are_written_as_concept_pages_under_tmp`; `python bench/knowledge/run.py --probe retrieval` exit 0, no guard line | pass |
| 8 | reviewer reads `bench/knowledge/data/retrieval/*.jsonl` | for review |

Input forms and failure paths the probe handles, each with its test:
- A line that is not UTF-8: `test_a_line_that_is_not_utf8_raises_with_file_and_line`. A JSON value other than an object: the `not an object` case of both bad-line tests.
- Pages (`test_a_bad_pages_line_raises_with_file_and_line`): a missing field (`lacks a field`), a repeated id (`repeats an id`), an id outside `concepts/` (`has an id outside concepts/`), an id with a capital and a space (`has an id with a capital and a space`), a lang other than `en`/`zh` (`has an unknown lang`), a zh page with Latin text (`breaks the lang rule`), a role other than `target`/`distractor` (`breaks the role rule`).
- Queries (`test_a_bad_queries_line_raises_with_file_and_line`): a missing field, a repeated id, a relevant id that is a distractor or no page, an unknown group, an en query of 7 words or with a word missing from the body, a zh query not in Chinese or not in the body, a zh-to-en query not in Chinese or with a relevant list that differs from the en row it translates. A zh-to-en row may name an en row that comes later in the file. `test_a_query_that_breaks_its_group_rule_raises_with_file_and_line`: an en query whose words are split across relevant bodies, an en query of numbers only, of punctuation only or with a number word, a zh query missing from one of its relevant bodies.
- Hybrid arm `unmeasured` with the cause when the embedding model load fails, the index build raises, the index build returns False (model2vec or sqlite-vec not importable), or the vector branch returns no hit for any query: `test_hybrid_arm_is_unmeasured_with_the_cause`. A missing model in an empty Hugging Face cache was also run by hand with the network blocked: `unmeasured`, `LocalEntryNotFoundError`, exit 0.
- `huggingface_hub` reads `HF_HUB_OFFLINE` once, at import. The probe also sets `huggingface_hub.constants.HF_HUB_OFFLINE` to True for the hybrid arm and restores the earlier value when the arm returns and when it raises: `test_hybrid_arm_makes_imported_hub_offline_and_restores_it[returns]`, `[raises]`. A run with `HTTPS_PROXY` pointing at a closed port gave the same record as an unblocked run.

Process deviation: while I was finding out why the vector branch returned no hit, a debug script I ran from the scratchpad, outside the probe and without `HF_HUB_OFFLINE`, made one metadata GET to `huggingface.co/api/models/minishlab/potion-base-8M/revision/main`. Nothing was downloaded; the model files were already in the local cache. Every later run was offline or behind the closed-port proxy.

Observed, not fixed (outside allow_paths):
- `search_pages` does not read `KB_DISABLE_VECTORS` (only `kb.query.hybrid.hybrid_search` does); its vector branch runs whenever the index file exists. The probe therefore runs the `bm25` arm before it builds the index.
- With sqlite-vec 0.1.9, `PRAGMA table_info(vec_pages)` returns an empty type for the `embedding` column and `float[N]` appears only in `sqlite_master.sql`, so `VectorIndex._read_stored_dim` returns 0 and `VectorIndex.query` returns `[]` for every query. Locally the hybrid arm is therefore `unmeasured: vector branch returned no hit for any query` although the model loads and the index builds (24 entries).
