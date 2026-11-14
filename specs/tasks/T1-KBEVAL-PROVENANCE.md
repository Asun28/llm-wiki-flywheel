---
id: T1-KBEVAL-PROVENANCE
title: "The `provenance` probe reports the trust value of each cited page after one `wrong` rating, whether `refine_page` accepts a body cut to 50, 10, 1 and 0 percent, and the share of pages whose sources all lie under `raw/captures/`"
status: merged
branch: T1-KBEVAL-PROVENANCE
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-PROVENANCE
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/provenance.py
  - bench/knowledge/tests/test_provenance.py
  - specs/tasks/T1-KBEVAL-PROVENANCE.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_provenance.py -q
dod_exit: 0
requirements:
  - R1. The arm `trust` shall, for k of 1, 3 and 10, call `kb.feedback.store.add_feedback_entry("bench question", "wrong", pages, path=<a new file under ctx.tmp>)` once with k page ids and report `trust_k<k>_p<i>` (the stored `trust` of the i-th page) and `wrong_k<k>_p<i>` (its stored `wrong` count), with `cases` 3.
  - R2. The arm `refine` shall, for a ratio of 50, 10, 1 and 0 percent, make a wiki under `ctx.tmp` with one page whose body is 20 different sentences and at least 2000 characters, call `kb.review.refiner.refine_page(page_id, new_body, "bench", wiki_dir=..., history_path=...)` with `new_body` the first ratio percent of the body's characters, and report `accepted_<ratio>` (1 when the page file's body after the call equals `new_body` with outer white space removed, else 0) and `refused_<ratio>` (1 when the call raised or its result holds an `error` key, else 0), with `cases` 4.
  - R3. The arm `captures` shall read the pages of `ctx.wiki` (every `*.md` file in a subdirectory, with its `source` frontmatter list) and report `cases` (the pages read), `pages_with_sources`, `pages_any_capture_source`, `pages_all_capture_sources` (every ref starts with `raw/captures/`), `refs_total`, `refs_captures`, and among the `pages_all_capture_sources` pages `stated_all_capture` (`confidence: stated`) and `confirmed_all_capture` (`belief_state: confirmed`).
  - R4. IF `ctx.wiki` holds no page, THEN the `captures` arm shall be `unmeasured` with the reason `no pages`.
  - R5. IF `add_feedback_entry` or the page write of R2 fails in a way other than a refusal by `refine_page`, THEN the probe shall let the exception reach the runner.
  - R6. The probe shall return `invariants` equal to `["I6", "I9"]`.
acceptance:
  - 1. `test_provenance.py`, `add_feedback_entry` replaced by a stub that writes a chosen score file: the arm reports 14 `trust_` and 14 `wrong_` metrics with the stub's values, and each k uses its own new file. [R1] [dod arm 2]
  - 2. Same file, `refine_page` replaced in turn by a stub that writes the new body, one that returns `{"error": "x"}` and leaves the page, and one that raises `ValueError`: `accepted_<ratio>` and `refused_<ratio>` are 1 and 0, 0 and 1, 0 and 1; the body passed for 50 percent has half the characters of the page body and the body passed for 0 percent is empty. [R2] [dod arm 2]
  - 3. Same file, a temporary wiki of six pages (no source, one capture ref, two capture refs, one capture and one article ref, one article ref, two capture refs with `confidence: stated` and `belief_state: confirmed`): every metric of R3 equals its hand-computed value; an empty wiki gives `unmeasured` with `no pages`. [R3] [R4] [dod arm 2]
  - 4. Same file: a stub `add_feedback_entry` that raises `OSError` makes the runner exit 1 with the probe name. [R5] [dod arm 2]
  - 5. Same file, the real functions with `demo/wiki` run through the runner: exit 0, `trust` and `refine` `measured`, every `trust_` metric between 0 and 1, for each ratio `accepted` and `refused` are not both 1, `invariants` equal to `["I6", "I9"]`. [R1] [R2] [R6] [dod arm 2]
depends_on: [T1-KBEVAL-HARNESS-3]
parallelizable_with: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-LINKER, T1-KBEVAL-CITATIONS, T1-KBEVAL-TRACE, T1-KBEVAL-REBUILD]
budget: 450
forbid: [any change under src/kb/ templates/ or tests/, a write under `ctx.wiki` or `ctx.raw` or to the checkout's feedback file, a model call or network request, a threshold or pass/fail judgement on a metric]
non_goals: [drift over repeated refine or re-ingest rounds (needs model calls, a later goal), `useful` and `incomplete` ratings, how search ranking uses trust, synthesis pages and query answers used as sources (no field records that today), the MCP tool `kb_refine_page` (the probe calls `refine_page` directly), any fix]
hygiene: "The lead said one `wrong` rating is split across the cited pages. Reading `add_feedback_entry` on 2026-11-13 showed a full `wrong` count on every cited page; the `trust` arm records which is true. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-PROVENANCE

## Deliverable
The first numbers for leads 7 and 8 of `intent/kb-baseline.md` and for invariants I6 and I9: what one `wrong` rating does to each cited page, how much of a page `refine_page` lets a caller delete, and how much of the wiki rests only on model-written captures.

## Why
Trust comes from user ratings alone, and one rating on an answer that cites ten pages lowers all ten whether or not they were the wrong ones. `refine_page` replaces the body after the frontmatter with what it is given, and BACKLOG lists the missing size check as HIGH. `raw/captures/` holds text a model wrote and is read as a raw source, so a page whose only sources are captures has no independent evidence.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_provenance.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence
Attempt 1. RED commit `7a116cf` (tests + stub probe that returns every arm measured with zero cases, no metrics and `invariants: []`; it calls no `kb` function and reads nothing): 23 failed, 0 passed. Every failure is an assertion: 19 `AssertionError`, 3 `Failed: DID NOT RAISE`, 1 runner exit-code assertion. GREEN commit: the real probe, 23 passed.

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1 [R1] | `test_trust_reports_the_stored_values_of_each_cited_page` (14 `trust_` and 14 `wrong_` metrics equal the stub's values, chosen distinct per k and position), `test_trust_calls_add_feedback_entry_once_per_k_with_a_new_file_under_tmp` (complete call list: k = 1, 3, 10; question, rating, notes; distinct ids; each path new, distinct and under `ctx.tmp`), `test_a_store_without_an_entry_for_a_cited_page_raises_naming_the_page` | pass |
| 2 [R2] | `test_refine_reports_accept_and_refuse_per_ratio[write-1-0, error-0-1, raise-0-1, silent-0-0]`, `test_refine_passes_the_first_ratio_percent_of_a_twenty_sentence_body` (body read from the page file by the stub: 20 distinct sentences, >= 2000 chars; 50 percent = `len // 2` prefix, 10 and 1 percent prefixes, 0 percent `""`), `test_refine_uses_its_own_wiki_and_history_under_tmp_for_each_ratio` (4 calls, notes `bench`, 4 distinct wikis and history paths under `ctx.tmp`, corpus bytes and mtimes unchanged) | pass |
| 3 [R3] [R4] | `test_captures_metrics_equal_hand_computed_values` (the six pages of the card, values worked out in the test comment), `test_captures_counts_only_files_in_subdirectories_and_only_all_capture_pages`, `test_captures_reads_a_single_string_source_and_crlf_frontmatter`, `test_a_wiki_with_no_page_makes_captures_unmeasured[empty, root files only]` | pass |
| 4 [R5] | `test_a_failing_feedback_store_makes_the_runner_exit_1_with_the_probe_name` (runner subprocess: exit 1, `provenance failed:`, `OSError`, no record), `test_a_failing_page_write_reaches_the_caller` (PermissionError from the probe's own page write propagates, `refine_page` never called) | pass |
| 5 [R1] [R2] [R6] | `test_demo_wiki_runs_through_the_runner_with_the_real_functions`, `test_the_real_stores_lie_under_tmp_and_no_model_function_runs` (runner subprocess on `demo/wiki` with the real functions wrapped by recorders; model entry points replaced by raising spies, none called; every feedback path, refine wiki and history path under the probe's `ctx.tmp`; no `guarded directory changed:`) | pass |

Input forms and failure paths of the captures arm (the corpus is the only input; the probe has no data files):
- `*.md` in a subdirectory, nested included; root files, non-`.md` files: `test_captures_counts_only_files_in_subdirectories_and_only_all_capture_pages`.
- `source` as a list, as a single string, missing: `test_captures_reads_a_single_string_source_and_crlf_frontmatter`, the six-page test. Read through `kb.utils.pages.normalize_sources`, the form `kb` itself reads.
- A ref in another form (`captures/x.md`) is not a capture ref; `all()` over refs, tested with a page holding one non-capture ref: `entities/other-form.md` and `entities/mixed.md`.
- `confidence` and `belief_state` compared exactly; other values (`inferred`, `uncertain`) not counted; stated and confirmed on a mixed page not counted.
- CRLF frontmatter: parsed (`crlf.md`).
- Frontmatter that fails to load (malformed YAML, `created: 2026-02-30`, bytes that are not UTF-8): page read with no sources, probe continues: `test_a_page_whose_frontmatter_fails_to_load_is_read_with_no_sources[3 cases]`.
- `FileNotFoundError` on read: page not read: `test_a_page_that_vanishes_before_it_is_read_is_not_counted`. Any other OSError (`PermissionError`) propagates: `test_a_page_that_cannot_be_read_for_another_reason_raises`.

Mutation checks (each applied alone to the GREEN probe, run, reverted; none committed):

| Mutation | Caught by |
|---|---|
| exception from `refine_page` not counted as refused | `test_refine_reports_accept_and_refuse_per_ratio[raise-0-1]` |
| page body compared without stripping | `...[write-1-0]` |
| stated/confirmed counted on any-capture pages | `test_captures_metrics_equal_hand_computed_values` |
| first page's trust reported for every position | `test_trust_reports_the_stored_values_of_each_cited_page` |
| one feedback file shared by every k | `test_trust_calls_add_feedback_entry_once_per_k_with_a_new_file_under_tmp` |
| body cut one character long | `test_refine_passes_the_first_ratio_percent_of_a_twenty_sentence_body` |
| root files counted as pages | `test_captures_counts_only_files_in_subdirectories_and_only_all_capture_pages` |
| every OSError on read skipped | `test_a_page_that_cannot_be_read_for_another_reason_raises` |
| only UnicodeDecodeError caught on parse | `test_a_page_whose_frontmatter_fails_to_load_is_read_with_no_sources[an impossible date]` |
| `error` key not counted as refused | `...[error-0-1]` |
| `accepted = 1 - refused` | `...[silent-0-0]` |
| page with no source counted as all-capture | `test_captures_metrics_equal_hand_computed_values` |

Measured on `demo/` (`python bench/knowledge/run.py --probe provenance`, exit 0, no guard line): every cited page gets `trust` 0.25 and `wrong` 1 for k = 1, 3 and 10, so one `wrong` rating is not split across the cited pages; `refine_page` accepted 50, 10 and 1 percent and refused 0 percent only; captures: 10 pages, 10 with sources, 15 refs, 0 capture refs, 0 all-capture pages.
