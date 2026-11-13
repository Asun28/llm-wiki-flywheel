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
depends_on: [T1-KBEVAL-HARNESS]
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
