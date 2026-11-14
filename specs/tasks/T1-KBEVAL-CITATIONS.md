---
id: T1-KBEVAL-CITATIONS
title: "The `citations` probe reports how many citations of pages outside the prompt context, and of pages that do not exist, `query_wiki` returns for scripted answers"
status: todo
branch: T1-KBEVAL-CITATIONS
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-CITATIONS
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/citations.py
  - bench/knowledge/data/citations/pages.jsonl
  - bench/knowledge/data/citations/questions.jsonl
  - bench/knowledge/tests/test_citations.py
  - specs/tasks/T1-KBEVAL-CITATIONS.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_citations.py -q
dod_exit: 0
requirements:
  - R1. `pages.jsonl` shall hold at least 12 pages (`id` unique, `title`, `body`) on at least two unrelated topics, and `questions.jsonl` at least 5 questions (`id` unique, `question`), each about one of the topics.
  - R2. IF a line of either file is not a JSON object, lacks a field or repeats an `id`, THEN the probe shall raise `ValueError` naming the file and the line number.
  - R3. For each question the probe shall call `kb.query.engine.query_wiki(question, wiki_dir)` twice on a wiki made under `ctx.tmp` from `pages.jsonl`, with the model call of `kb.query.engine` replaced by a function that makes no network request, first returning an answer with no citation to read `context_pages`, then returning the scripted answer of R4.
  - R4. The scripted answer shall cite, in the `[[page id]]` form, one page of `context_pages` (class `in-context`), two pages of the wiki that are not in `context_pages` (class `out-of-context`), two ids of the form `concepts/missing-<n>` that are no page of the wiki (class `nonexistent`) and one id that starts with `../` (class `traversal`).
  - R5. IF `context_pages` is empty, differs between the two calls, or leaves fewer than two pages outside it, THEN the probe shall raise `ValueError` naming the question id.
  - R6. The arm `scripted` shall report `cases` (the question count) and, for each class, `injected_<class>` and `returned_<class>` (the citations of that class whose path is in the result's `citations`), and `citation_keys_uniform` (1 when every returned citation has the same key set, else 0).
  - R7. The probe shall return `invariants` equal to `["I1"]`.
acceptance:
  - 1. `test_citations.py`: the committed files load under R1 and R2 with the minimum counts. [R1] [dod arm 2]
  - 2. Same file, one test per cause of R2 for each file: `ValueError` whose message holds the file name and the line number. [R2] [dod arm 2]
  - 3. Same file, `query_wiki` replaced by a stub with a fixed `context_pages` that returns as `citations` a chosen subset of the cited paths: the scripted answer the stub receives through the replaced model function holds the six citations of R4 with the classes of R4, and `injected_<class>`, `returned_<class>` and `citation_keys_uniform` equal hand-computed values. [R3] [R4] [R6] [dod arm 2]
  - 4. Same file, one test per cause of R5: `ValueError` whose message holds the question id. [R5] [dod arm 2]
  - 5. Same file, the committed set run through the runner with the real `query_wiki`: exit 0, the arm `measured`, `cases` equal to the question count, `injected_in-context` equal to `cases`, `injected_out-of-context` and `injected_nonexistent` equal to twice `cases`, `returned_traversal` equal to 0, `invariants` equal to `["I1"]`, and the replaced model function was called and no other model function was. [R3] [R6] [R7] [dod arm 2]
depends_on: [T1-KBEVAL-HARNESS-3]
parallelizable_with: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-LINKER, T1-KBEVAL-TRACE, T1-KBEVAL-REBUILD, T1-KBEVAL-PROVENANCE]
budget: 450
forbid: [any change under src/kb/ templates/ or tests/, a model call or network request, a threshold or pass/fail judgement on a count]
non_goals: [whether a cited page supports the sentence that cites it (needs labels on real answers, a later goal), the legacy `[source: ...]` and `[ref: ...]` citation forms (not injected), citations of `raw/` paths (not injected), the MCP and CLI paths that call `query_wiki` (the probe calls the function directly), any fix]
hygiene: "`returned_traversal` is a control: `extract_citations` drops a path that holds `..`, so the value is expected to be 0. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-CITATIONS

## Deliverable
The first number for lead 4 of `intent/kb-baseline.md`: of the citations a model invents, how many come back in the result of `query_wiki` in the same form as a citation of a page the model was shown.

## Why
`query_wiki` sets `citations = extract_citations(answer)` and returns it; a comment beside it says the extracted citations "may reference pages outside context". A scripted answer with known citations measures that without a model: the correct count for the `out-of-context` and `nonexistent` classes is known before the run.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_citations.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED commit `1e34818`, GREEN commit `176c317`. Tests: `bench/knowledge/tests/test_citations.py`.

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. committed files load under R1 and R2 with the minimum counts | `test_committed_files_load_with_the_minimum_counts` (14 pages, 2 topics, 6 questions; ids compared with an independent JSON read) | pass |
| 2. one `ValueError` per cause of R2 for each file, naming file and line | `test_a_bad_pages_line_raises_with_file_and_line` (11 causes, line 6), `test_a_bad_questions_line_raises_with_file_and_line` (9 causes, line 3) | pass |
| 3. scripted answer holds the six citations of R4; counts equal hand-computed values | `test_the_scripted_answer_holds_the_six_citations_of_r4`, `test_counts_equal_hand_computed_values`, `test_citation_keys_uniform_is_zero_when_one_citation_has_another_key_set`, `test_query_wiki_is_called_twice_per_question_on_a_wiki_under_tmp`, `test_the_model_function_is_restored_after_the_run` | pass |
| 4. one `ValueError` per cause of R5, naming the question id | `test_a_bad_context_raises_naming_the_question` (empty, differs between the calls, fewer than two outside; fails on `q-two`, the second question) | pass |
| 5. committed set through the runner with the real `query_wiki` | `test_committed_set_runs_through_the_runner`, `test_only_the_replaced_model_function_is_called` (in-process `run.main`; spies that record and raise on `kb.utils.llm.call_llm`, `call_llm_json`, `get_client`, `_make_api_call`, `kb.utils.cli_backend.call_cli`, `kb.query.rewriter.call_llm`, `kb.query.engine._suggest_rephrasings`; a pass-through spy on `kb.query.engine.extract_citations` sees 2 answers per question, the first without a citation, the second with 6) | pass |

RED against the stub (`run` returns the arm measured with 0 cases and no metrics; loaders return empty; no `kb` call): 30 failed, 1 passed. Failures: 23 `pytest.raises` DID NOT RAISE, 7 `AssertionError`; no import or missing-file error. The 1 pass is `test_the_model_function_is_restored_after_the_run`, which holds for a stub that never replaces the function. GREEN: 31 passed.

Expected values come from the test's own sources: `EXPECTED_SMALL` is computed by hand from the stub's `KEEP` table and R4; the stub classifies cited paths with its own pattern and the fixed context; acceptance 5 counts come from the row count of `questions.jsonl`.

Mutation checks (applied to a copy of the probe, run, then reverted; none committed):

| Mutation | Tests failing |
|---|---|
| `returned_<class>` counted from the answer instead of the result's `citations` | 2 |
| `citation_keys_uniform` constant 1 | 1 |
| empty-context check removed | 1 |
| differs-between-calls check removed | 1 |
| fewer-than-two-outside check removed | 1 |
| `call_llm` not restored | 4 |
| question topic check removed | 1 |
| question word check removed | 1 |
| traversal citation left out of the answer | 3 |
| first `query_wiki` call skipped (fixed context) | 5 |
| page id of the `concepts/missing-<n>` form accepted | 1 |

Input forms and failure paths:

| File | Rule | Test case |
|---|---|---|
| both | line not JSON | `not JSON` |
| both | line not a JSON object | `not an object` |
| both | field missing | `lacks a field` |
| both | repeated `id` | `repeats an id` |
| pages | `id` not `concepts/<slug>` | `has an id outside concepts/`, `has an id with a capital and a space` |
| pages | `id` of the form `concepts/missing-<n>` | `has an id of the nonexistent form` |
| pages | `topic` not a lower-case slug | `has a topic that is not a slug` |
| pages | `title` not a non-empty string | `has a title that is not a string`, `has an empty title` |
| pages | `body` holds no word | `has a body without a word` |
| questions | `id` not a lower-case slug | `has an id that is not a slug` |
| questions | `question` holds no word or is not a string | `has a question without a word`, `has a question that is not a string` |
| questions | `topic` is the topic of no page | `has a topic of no page` |
| questions | `why` empty | `has an empty why` |
| run | `context_pages` empty, differs between the calls, fewer than two pages outside | acceptance 4 test |

Measured on the committed set (6 questions): injected in-context 6, out-of-context 12, nonexistent 12, traversal 6; returned in-context 6, out-of-context 12, nonexistent 12, traversal 0; `citation_keys_uniform` 1.
