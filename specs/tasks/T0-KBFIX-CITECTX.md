---
id: T0-KBFIX-CITECTX
title: "query_wiki returns only citations to pages and raw files that were in the prompt context (#189)"
status: merged
branch: T0-KBFIX-CITECTX
worktree: D:\wt\llm-wiki-flywheel\T0-KBFIX-CITECTX
allow_paths:
  - src/kb/query/engine.py
  - src/kb/query/citations.py
  - tests/test_kbfix_query_citation_context.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T0-KBFIX-CITECTX.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_query_citation_context.py tests/test_query.py tests/test_cycle9_query_engine.py tests/test_workflow_e2e.py tests/test_cycle23_workflow_e2e.py tests/test_e2e_karpathy_five_cycle.py tests/test_mcp_core.py tests/test_cli.py tests/test_kbfix_query_default_wiki_dir.py bench/knowledge/tests/test_citations.py -q
dod_exit: 0
requirements:
  - R1. WHEN the answer cites a wiki page whose id is in `context_pages`, `query_wiki` shall return that citation in `citations`, unchanged in shape (`type`, `path`, `context`).
  - R2. WHEN the answer cites a wiki page whose id is not in `context_pages`, `query_wiki` shall leave it out of `citations` and return it in `rejected_citations` with `reason` = `out_of_context` if the page file exists under the wiki directory, else `nonexistent`.
  - R3. WHEN the answer cites a raw file (`type: raw`), `query_wiki` shall return it in `citations` only if that raw id entered the prompt through the raw-source fallback; otherwise it goes to `rejected_citations` with `reason` = `out_of_context` if the file exists under the raw directory, else `nonexistent`.
  - R4. Ids are compared case-insensitively (`str.lower()` on both sides); `context_pages` ids are already lower-case (`kb.utils.pages.page_id`).
  - R5. The `answer` text is returned unchanged. `rejected_citations` is always present in the result dict (an empty list when nothing is rejected, including the no-match and low-confidence paths).
acceptance:
  - 1. `test_kbfix_query_citation_context.py`: in the `tmp_kb_env` sandbox with three concept pages written as bytes, `KB_DISABLE_VECTORS=1`, and `kb.query.engine.call_llm` replaced by a stub whose answer cites one in-context page, one existing page outside `context_pages`, and one missing page: `citations` paths equal the in-context page only; `rejected_citations` holds the other two with reasons `out_of_context` and `nonexistent`; `answer` equals the stub text. [R1] [R2] [R5] [dod arm 2]
  - 2. Same file: an answer citing the in-context page id in upper case is accepted. [R4] [dod arm 2]
  - 3. Same file: with only a summary page in the wiki so the raw fallback fires, a `[ref: raw/articles/<file>]` citation of the raw file that entered the prompt is accepted, and a citation of a raw file that exists but did not enter the prompt is rejected with `out_of_context`. [R3] [dod arm 2]
  - 4. Same file: the no-match path returns `rejected_citations == []`. [R5] [dod arm 2]
  - 5. `python bench/knowledge/run.py --probe citations` on the candidate reports `returned_out-of-context` = 0, `returned_nonexistent` = 0, `returned_traversal` = 0, `returned_in-context` = 6 (reviewer-verified).
  - 6. Every DoD test file passes and no existing test is edited; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 120
sweep: "`extract_citations` callers: `query/engine.py:1152` (the only production caller); `query/formats` adapters read `result_dict['citations']` and keep working on the filtered list. Consumers of `query_wiki` results: `cli.py` query command, `mcp/core.py` `kb_query(use_api=True)`, `query/formats/*`. Existing tests asserting citations: `test_query.py:270` (cites in-context `concepts/rag`), `test_cycle9_query_engine.py:179` (cites the raw file that entered the prompt via fallback), `test_workflow_e2e.py:95` (cites in-context `entities/anthropic` plus `raw/articles/sample`, not in prompt), `test_cycle23_workflow_e2e.py:133` and `test_e2e_karpathy_five_cycle.py:148` (list type only), bench `test_citations.py` (no hard-coded `returned_*` counts except traversal = 0)."
forbid:
  - "a change to `extract_citations` behaviour or signature (the bench spy counts one call per answer)"
  - "editing the answer text"
  - "a second model call"
  - "any edit to an existing test"
  - "a model call or network request in tests"
non_goals:
  - "default MCP mode (`kb_query` without `use_api`): no answer passes through `query_wiki`; follow-up issue to be filed"
  - "showing `rejected_citations` in CLI or MCP output"
  - "updating the committed bench baseline `bench/knowledge/summary.json`"
diagnosis:
  root_cause: "`_query_wiki_body` sets `citations = extract_citations(answer)` (`src/kb/query/engine.py:1152`) and returns it as is. `extract_citations` (`src/kb/query/citations.py:15`) filters path shape only. The set of ids in the prompt (`ctx['context_pages']`, plus the raw ids appended to `raw_sections` at `engine.py:1068-1083`) is never compared with the citations. Reproduced on main a179025 by the bench probe: 12/12 out-of-context and 12/12 nonexistent citations returned."
  same_class: "none known; `stale_citations` (`engine.py:1158`) already uses `context_pages` instead of the extracted citations."
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixtures as bytes. Every call runs inside `tmp_kb_env`. Stub `kb.query.engine.call_llm`. RED: acceptance 1-4 fail on the unfixed code (out-of-context citations returned, no `rejected_citations` key)."
---

# T0-KBFIX-CITECTX

## Deliverable
`query_wiki` returns in `citations` only the pages and raw files that were in the prompt. Every other extracted citation is returned in `rejected_citations` with a reason (`out_of_context` or `nonexistent`). The answer text is unchanged.

## Why
Issue #189. A caller reading `citations` cannot tell a grounded citation from one the model made up; the bench probe returns 12/12 out-of-context and 12/12 nonexistent citations.

## Owner decisions (2026-11-23)
1. Rejected citations go under a separate key with a reason per entry.
2. Answer text is left unchanged; rejection is reported only.
3. Raw citations are accepted only when that raw file entered the prompt.
4. Default MCP mode is out of scope; a follow-up issue is filed.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_query_citation_context.py tests/test_query.py tests/test_cycle9_query_engine.py tests/test_workflow_e2e.py tests/test_cycle23_workflow_e2e.py tests/test_e2e_karpathy_five_cycle.py tests/test_mcp_core.py tests/test_cli.py tests/test_kbfix_query_default_wiki_dir.py bench/knowledge/tests/test_citations.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED on the unfixed code: `test_only_in_context_citations_are_returned` (citations held `concepts/tokenizer` and `concepts/missing-page`), `test_citation_id_comparison_ignores_case`, `test_raw_citation_accepted_only_when_it_entered_the_prompt` and `test_no_match_path_has_empty_rejected_citations` (`KeyError: 'rejected_citations'`): 4 failed.

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. in-context kept, out-of-context and nonexistent rejected with reasons, answer unchanged | `test_only_in_context_citations_are_returned` | pass |
| 2. upper-case id of the in-context page accepted | `test_citation_id_comparison_ignores_case` | pass |
| 3. raw citation accepted only when it entered the prompt | `test_raw_citation_accepted_only_when_it_entered_the_prompt` | pass |
| 4. no-match path: `rejected_citations == []` | `test_no_match_path_has_empty_rejected_citations` | pass |
| 5. bench probe | `python bench/knowledge/run.py --probe citations`: `returned_in-context=6 returned_nonexistent=0 returned_out-of-context=0 returned_traversal=0` | pass (reviewer-verified) |
| 6. DoD green, no existing test edited, CHANGELOG / CHANGELOG-history entries, CLAUDE.md counts | DoD below; `git diff main --stat -- tests/` lists only the new file; `python scripts/verify_docs.py`: docs in sync (4005 tests, 230 files) | pass (reviewer-verified) |

Attempt 2 (R3 decision 1 repair, 3 findings). RED on the blocked candidate 28b9dbb with the new tests copied in: `test_raw_form_citation_of_a_wiki_page_is_not_accepted`, `test_truncated_raw_section_counts_only_with_header_and_content[one-char]`, `[header-only]` and `test_upper_case_raw_prefix_is_probed_under_the_raw_dir` 4 failed; `[header-plus-content]` passed (control).

| R3 finding | Proving test | Result |
|---|---|---|
| F1 wiki/raw allowance shared | `test_raw_form_citation_of_a_wiki_page_is_not_accepted` | pass |
| F2 truncated raw section counted | `test_truncated_raw_section_counts_only_with_header_and_content` (one-char, header-only, header-plus-content) | pass |
| F3 `RAW/` prefix probe | `test_upper_case_raw_prefix_is_probed_under_the_raw_dir` | pass |

Input forms and paths the repair hunks handle:

| Hunk | Input form or path | Test |
|---|---|---|
| `partition_citations` per-type sets | wiki citation of an in-context page | `test_only_in_context_citations_are_returned` |
| | raw-form `[ref: <wiki id>]` citation, same id in `context_pages` | `test_raw_form_citation_of_a_wiki_page_is_not_accepted` |
| | raw citation of a raw id in the prompt | `test_raw_citation_accepted_only_when_it_entered_the_prompt` |
| | upper-case wiki id | `test_citation_id_comparison_ignores_case` |
| raw prefix match | `raw/...` (lower-case) existing, out of prompt | `test_raw_citation_accepted_only_when_it_entered_the_prompt` |
| | `RAW/...` existing, out of prompt | `test_upper_case_raw_prefix_is_probed_under_the_raw_dir` |
| | raw-type path with no `raw/` prefix (`concepts/hydration`) | `test_raw_form_citation_of_a_wiki_page_is_not_accepted` (`nonexistent`) |
| truncated raw section | budget 1 char (header cut) | `[one-char]` |
| | budget = header length exactly | `[header-only]` |
| | header + 10 chars of content | `[header-plus-content]` |
| | section fits whole | `test_raw_citation_accepted_only_when_it_entered_the_prompt` |

Same class elsewhere: `_build_query_context` already records a truncated wiki page only when `remaining > header_len` (`engine.py:784`) and returns no page when `effective_max <= len(header)` (`engine.py:840`).

Attempt 3 (R3 decision 2 repair, 3 findings). RED on the blocked candidate 34a0a96 with the new tests copied in: `test_wiki_reason_finds_a_mixed_case_file_name`, `test_raw_reason_ignores_case_beyond_the_prefix`, `test_stat_error_on_a_cited_name_rejects_it_and_keeps_the_answer` 3 failed. (A first version patched `Path.exists`, which the old `is_file()` probe never calls, and passed on the old code; the tests now patch `Path.stat`, which `exists`, `is_file` and `is_dir` all call.)

| R3 finding | Proving test | Result |
|---|---|---|
| F1 wiki file name differs in case from the id | `test_wiki_reason_finds_a_mixed_case_file_name` | pass |
| F2 raw path differs in case beyond the prefix | `test_raw_reason_ignores_case_beyond_the_prefix` | pass |
| F3 `OSError` from the probe aborts the query | `test_stat_error_on_a_cited_name_rejects_it_and_keeps_the_answer` | pass |
| fixture emulates a case-sensitive filesystem | `test_case_sensitive_stat_fixture_hides_a_case_variant` | pass |

Input forms and paths of `_is_file_ignoring_case`: exact-case segment exists (all earlier tests); segment differs in case, found by listing (F1 wiki, F2 raw directory and file segments); no segment matches (`raw/articles/absent.md` -> `nonexistent`, F2 test); parent is not a directory (`concepts/missing-page` -> listing finds nothing, `test_only_in_context_citations_are_returned`); `OSError` from `stat` (F3 test). An `OSError` from `iterdir` is caught by the same `except` (not separately tested).

Attempt 4 (R3 decision 3 repair, 1 finding). The case-insensitive segment walk is removed, not patched: the reason is a lookup of the lower-cased citation path in `_lower_relative_files(base)`, the lower-cased relative paths of the files under the wiki or raw directory. No model-written path is passed to `stat`.

RED/GREEN on a real case-sensitive filesystem (WSL Ubuntu, ext4 `/tmp`, Python 3.12, `citations.py` loaded by path with `python3 -I`): blocked candidate 15c5cac: `raw sibling case dirs` and `raw case beyond prefix` FAIL (`nonexistent`); repair: all 5 cases PASS (wiki mixed-case file, raw sibling case dirs, raw case beyond prefix -> `out_of_context`; raw missing, real 300-character name -> `nonexistent`).

| R3 finding | Proving test | Result |
|---|---|---|
| F1 sibling directories differing in case | `test_raw_reason_checks_every_case_variant_directory` (skipped on Windows, runs on Linux CI) and the WSL check above | pass (WSL), skip (Windows) |

Input forms and paths of `_lower_relative_files`: file name differs in case at the last segment (`test_wiki_reason_finds_a_mixed_case_file_name`), at directory and file segments (`test_raw_reason_ignores_case_beyond_the_prefix`), sibling directories differing in case (decision-3 test, WSL); file absent (`raw/articles/absent.md`, `concepts/missing-page`); model-written 300-character name, never stat'd (`test_stat_error_on_a_cited_name_rejects_it_and_keeps_the_answer`, WSL real `ENAMETOOLONG`); `OSError` while listing returns the files seen so far (not separately tested).
