---
id: T1-KBEVAL-REBUILD
title: "The `rebuild` probe reports the files a second ingest changes, the page differences between three ingest orders, and whether `find_changed_sources` sees a model id change, a template change and a source change"
status: merged
branch: T1-KBEVAL-REBUILD
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-REBUILD
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/rebuild.py
  - bench/knowledge/data/rebuild/sources.jsonl
  - bench/knowledge/data/rebuild/extractions.json
  - bench/knowledge/tests/test_rebuild.py
  - specs/tasks/T1-KBEVAL-REBUILD.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_rebuild.py -q
dod_exit: 0
requirements:
  - R1. `sources.jsonl` shall hold at least 6 rows with `path` (unique, `articles/<name>.md`) and `text`, and `extractions.json` shall map each `path` to an extraction that `kb.ingest.pipeline.ingest_source` accepts for source type `article`, such that at least 3 entity names and at least 3 concept names each occur in the extractions of at least 2 sources.
  - R2. IF a line of `sources.jsonl` is not a JSON object, lacks a field or repeats a `path`, or a `path` has no extraction, or an extraction names no source, THEN the probe shall raise `ValueError` naming the file and the line number or the path.
  - R3. The probe shall write the sources under a raw directory in `ctx.tmp` and ingest each with `ingest_source(path, "article", extraction, wiki_dir=..., raw_dir=...)`, so that no model is called.
  - R4. The arm `idempotence` shall ingest the sources in `path` order into one wiki, take the sha256 of every file under it, ingest them again in the same order, and report `cases` (the source count), `files_after_first`, `files_changed_by_second` (files added, removed or with another hash) and `page_files_changed_by_second` (those of them in a subdirectory of the wiki).
  - R5. The arm `order` shall ingest the sources into three separate wikis in `path` order, in reverse `path` order and in ascending order of the sha256 of `path`, and report, for the pairs `reverse` and `hashed` against `path` order, `page_set_equal_<pair>` (1 or 0, over the files in subdirectories), `pages_differing_bytes_<pair>` and `pages_differing_lines_<pair>` (pages in both whose non-empty lines differ as multisets).
  - R6. The arm `scan` shall, on a wiki and raw directory left by one ingest of all sources, call `kb.compile.compiler.find_changed_sources(raw_dir, manifest_path, save_hashes=False)` and report `listed_clean` (the sources listed with nothing changed), then `sees_model_change` after setting `CLAUDE_SCAN_MODEL`, `CLAUDE_WRITE_MODEL` and `CLAUDE_ORCHESTRATE_MODEL` to other ids, `sees_template_change` after appending a line to `article.yaml` in the temporary project root, and `sees_source_change` after appending a line to one source, each 1 when the call lists at least one source and else 0, with each change undone before the next.
  - R7. IF `listed_clean` is not 0, THEN the `scan` arm shall be `unmeasured` with a reason that holds the count.
  - R8. The probe shall restore the three environment variables to their earlier state and shall write nothing outside `ctx.tmp` and the temporary project root.
  - R9. The probe shall return `invariants` equal to `["I3", "I4"]`.
acceptance:
  - 1. `test_rebuild.py`: the committed files load under R1 and R2 with at least 6 sources, and at least 3 entity names and 3 concept names occur in two or more extractions. [R1] [dod arm 2]
  - 2. Same file, one test per cause of R2: `ValueError` whose message holds the file name and the line number or the path. [R2] [dod arm 2]
  - 3. Same file, `ingest_source` replaced by a stub that writes chosen files: `files_after_first`, `files_changed_by_second` and `page_files_changed_by_second` equal hand-computed values for a second pass that adds one page, rewrites one page and rewrites one root-level file. [R4] [dod arm 2]
  - 4. Same file, the same stub writing order-dependent pages: `page_set_equal_<pair>`, `pages_differing_bytes_<pair>` and `pages_differing_lines_<pair>` equal hand-computed values, and two pages with the same lines in another order count in `bytes` and not in `lines`. [R5] [dod arm 2]
  - 5. Same file, `find_changed_sources` replaced by a stub: the three `sees_` metrics follow the stub's answers, the three variables hold other ids only during the model step and their earlier values after it, and a stub that lists a source on the clean call gives `unmeasured` with the count in the reason. [R6] [R7] [R8] [dod arm 2]
  - 6. Same file, the committed set run through the runner with the real functions and a model function that raises when called: exit 0, `idempotence` and `order` `measured` with `cases` equal to the source count, `scan` `measured` or `unmeasured` with a reason, `invariants` equal to `["I3", "I4"]`. [R3] [R9] [dod arm 2]
depends_on: [T1-KBEVAL-HARNESS-3]
parallelizable_with: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-LINKER, T1-KBEVAL-CITATIONS, T1-KBEVAL-TRACE, T1-KBEVAL-PROVENANCE]
budget: 700
forbid: [any change under src/kb/ templates/ or tests/, a write to the checkout's `templates/` (the template step edits the copy in the temporary project root), a model call or network request, a time or duration in the record, a threshold or pass/fail judgement on a metric]
non_goals: [`compile_wiki` (it calls `ingest_source` with no extraction, so a model would run), the prompt text and the backend as cache inputs (no call is made, so neither can be varied), byte-equal rebuilds on two machines, a run that crosses midnight (the `updated` date of a page may differ between passes; rerun), ingest timing and token cost, any fix]
hygiene: "The extractions stand in for the model, so the arms measure the deterministic part of ingest only: what the code does with equal extractions. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-REBUILD

## Deliverable
The first numbers for lead 6 of `intent/kb-baseline.md` and for invariants I3 and I4: whether ingesting the same source twice is a no-op, whether the order of ingest changes the pages, and which input changes the changed-source scan can see.

## Why
`compile/compiler.py` keys its manifest on the source hash and the template hashes. The lead says the model id is not in the key, so a model change leaves every source marked as compiled. Shared entity and concept pages are built by appending a section per source, so the order of ingest may change them. Both are measurable without a model because `ingest_source` takes a finished extraction.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_rebuild.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED commit `900bd66`, GREEN commit `7f5d518`. Tests: `bench/knowledge/tests/test_rebuild.py`.

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. committed files load under R1 and R2; at least 6 sources; 3 entity and 3 concept names in two or more extractions | `test_committed_files_load_with_the_minimum_counts` (6 sources; counts read from the JSON by the test; the stub ingest receives each committed text byte for byte and each committed extraction) | pass |
| 2. one `ValueError` per cause of R2, naming the file and the line or path | `test_a_bad_sources_line_raises_with_file_and_line` (12 causes, line 5), `test_a_bad_extraction_raises_with_file_and_path` (12 causes, each names the path), `test_an_extractions_file_that_is_not_json_raises_with_file_and_line` (line 3), `test_an_extractions_file_that_is_not_an_object_raises_with_file`; each also asserts no ingest ran | pass |
| 3. idempotence counts equal hand-computed values for a second pass that adds a page, rewrites a page and rewrites a root file | `test_idempotence_counts_equal_hand_computed_values` (7, 3, 2; unchanged files are rewritten with equal bytes), `test_a_file_removed_by_the_second_pass_counts_as_changed` (7, 1, 1), `test_ingest_is_called_once_per_source_per_pass_on_wikis_under_tmp` (complete call list: path order twice, then path, reverse, sha256, path; arguments, raw dir, manifest and wiki of each call under `ctx.tmp`; `HASH_MANIFEST` restored) | pass |
| 4. order counts equal hand-computed values; same lines in another order count in bytes and not in lines | `test_order_counts_equal_hand_computed_values` (reverse 0/2/1, hashed 1/1/0; `entities/shared.md` differs in bytes only; root `log.md` differs and is not counted), `test_a_page_that_differs_by_a_blank_line_counts_in_bytes_not_in_lines`, `test_the_hashed_order_literal_matches_sha256` | pass |
| 5. `sees_` metrics follow the stub; variables hold other ids only during the model step; clean listing gives `unmeasured` with the count | `test_scan_metrics_follow_the_answers_of_each_step` (two answer sets, 0/1/1 and 1/0/0; the stub names each step by what it observes), `test_each_scan_step_changes_one_input_and_undoes_it`, `test_a_source_listed_on_the_clean_call_makes_the_arm_unmeasured` (3 in the reason, no further call), `test_a_scan_that_raises_leaves_every_input_as_it_was` (model, template, source), `test_a_template_outside_the_project_root_is_not_edited` | pass |
| 6. committed set through the runner with the real functions and model functions that raise | `test_committed_set_runs_through_the_runner`, `test_the_real_ingest_runs_once_per_source_per_pass_and_no_model_function_runs` (subprocess runner; the probe file in the temporary probes dir wraps the real probe, replaces `kb.utils.llm.call_llm`, `call_llm_json`, `get_client`, `_make_api_call`, `kb.utils.cli_backend.call_cli`, `kb.ingest.extractors.call_llm_json`, `extract_from_source` in `kb.ingest.extractors` and `kb.ingest.pipeline`, and `kb.query.embeddings.rebuild_vector_index` with functions that record and raise; records 0 such calls and 36 real ingests in the expected order) | pass |

RED against the stub (`run` returns three arms measured with 0 cases and no metrics and `invariants` `[]`; no `kb` call): 42 failed, 1 passed. Failures: 30 `pytest.raises` DID NOT RAISE, 12 `AssertionError`; no import or missing-file error. The 1 pass is `test_the_hashed_order_literal_matches_sha256`, which checks the test's own literal. GREEN: 43 passed.

Expected values come from the test: the stub writers fix which files each call writes, and the counts are worked out by hand from them in the comments; the sha256 order is a literal checked against `hashlib`; acceptance 6 counts come from the row count of `sources.jsonl`.

Mutation checks (applied to the probe, run, then restored from `7f5d518`; none committed):

| Mutation | Tests failing |
|---|---|
| second ingest skipped | 3 (both idempotence count tests, call list) |
| changed files = added or removed only (hash ignored) | 1 |
| `page_files_changed_by_second` = all changed files | 1 |
| reverse order = path order | 3 |
| empty lines kept in the line multiset | 1 |
| lines compared as bytes | 2 |
| scan counts only the `changed` list | 2 |
| model variables not restored | 6 |
| appended line not removed | 5 |
| no `unmeasured` on a clean listing | 1 |
| list items of an extraction not checked (`all()` rule) | 3 |
| `HASH_MANIFEST` not redirected to the case | 1 |
| constant result (the RED stub) | 42 |

Input forms and failure paths:

| Form | Rule | Test |
|---|---|---|
| `sources.jsonl` line | JSON object with `path` and `text`, both non-empty strings; `path` matches `articles/<slug>.md`; `path` unique | `test_a_bad_sources_line_raises_with_file_and_line` |
| `extractions.json` file | valid JSON (error names the line), top level an object | the two `extractions_file` tests |
| `extractions.json` entry | one per source and none for another path; an object; `title` a non-empty string; `author` and the other summary string fields strings when present; `entities_mentioned` and `concepts_mentioned` present and every item a non-empty string; `key_claims` every item a non-empty string when present | `test_a_bad_extraction_raises_with_file_and_path` |
| template to edit | `article.yaml` under `KB_PROJECT_ROOT` and not in the checkout, else `ValueError` before any change | `test_a_template_outside_the_project_root_is_not_edited` |
| scan call raising in a step | variables, template and source restored | `test_a_scan_that_raises_leaves_every_input_as_it_was` |

Deviation to review: `ingest_source` is called with `_skip_vector_rebuild=True` in addition to the arguments of R3. Without it each ingest rebuilds the vector index, which loads the embedding model (a download where it is not cached, as on CI) and writes `.data/vector_index.db` beside the wiki. The index is outside the wiki, so no measured file depends on it.

Measured on the committed set (`python bench/knowledge/run.py --probe rebuild`, exit 0, no guard line):
- idempotence: `files_after_first=17 files_changed_by_second=2 page_files_changed_by_second=0` (the two are the root files `contradictions.md` and `log.md`).
- order: `page_set_equal_reverse=1 pages_differing_bytes_reverse=9 pages_differing_lines_reverse=9`, and the same three values for `hashed`. The 9 are the 4 entity and 5 concept pages shared by sources: the first source writes "Initial extraction: concept page created" and a quoted `source:` item, later ones "source reference added" and an unquoted item, so which source comes first changes the lines.
- scan: `unmeasured`, `listed_clean=6`. `ingest_source` writes no `_template/<type>` keys to the manifest, so `find_changed_sources` reports every article as changed by a template change on the first call; the three `sees_` steps do not run.

Not covered: the wiki starts with the page subdirectories only, so `index.md` and `_sources.md` do not exist and ingest skips their updates (it logs a warning); the second-ingest effect on them is not measured. Also seen in the order arm: the linker writes a link inside a source-path heading (`### From raw/articles/high-[[concepts/hydration|Hydration]].md`).
