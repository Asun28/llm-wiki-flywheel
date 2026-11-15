---
id: T1-KBFIX-SHRINK
title: "`refine_page` refuses a new body under half the current body unless `allow_shrink=True`, which the review history records; `kb_refine_page` passes the flag through (#162)"
status: todo
branch: T1-KBFIX-SHRINK
worktree: D:\wt\llm-wiki-flywheel\T1-KBFIX-SHRINK
plan_ref: plans/kb-defects-1.md#order-of-work
allow_paths:
  - src/kb/review/refiner.py
  - src/kb/mcp/quality.py
  - src/kb/config.py
  - tests/test_kbfix_refine_shrink_guard.py
  - BACKLOG.md
  - docs/reference/mcp-servers.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T1-KBFIX-SHRINK.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_refine_shrink_guard.py tests/test_refiner.py tests/test_review.py tests/test_cycle19_refiner_two_phase.py tests/test_cycle88_rollback_reporting.py tests/test_mcp_quality_new.py tests/test_mcp_phase2.py tests/test_fixes_v050.py -q
dod_exit: 0
requirements:
  - R1. `kb.config` shall define `REFINE_MIN_BODY_RATIO = 0.5`, read by `refine_page` at call time.
  - R2. IF the new body has fewer than `REFINE_MIN_BODY_RATIO` times the characters of the current body, both counted after CRLF to LF and `strip()`, and `allow_shrink` is not true, THEN `refine_page` shall return an `error` holding both lengths and the ratio, and shall leave the page bytes and the review history unchanged.
  - R3. The check of R2 shall run after the frontmatter gates and the empty-body guard and before the pending history row; a current body of length 0 shall have no floor.
  - R4. WHEN `allow_shrink=True` is passed and the floor of R2 is crossed, `refine_page` shall write the page and its review-history row for that attempt shall hold `allow_shrink: true`, `previous_body_length` and `new_body_length`; rows of writes that do not cross the floor shall hold none of these keys.
  - R5. `refine_page` shall take `allow_shrink` as a keyword-only argument defaulting to false, and `kb_refine_page` shall accept `allow_shrink: bool = False` and pass it to `refine_page`.
acceptance:
  - 1. `test_kbfix_refine_shrink_guard.py`: on a page whose stripped body has 200 characters, a 99-character body is refused (error holds `200`, `99` and the ratio; page bytes and history file unchanged) and a 100-character body is accepted. [R1] [R2] [dod arm 2]
  - 2. Same file: a 2-character body (1%) is refused; the same body with `allow_shrink=True` is written, and the attempt's history row holds `allow_shrink: true`, `previous_body_length: 200`, `new_body_length: 2`; the row of the accepted 100-character write holds none of the three keys. [R2] [R4] [dod arm 2]
  - 3. Same file: a page with malformed frontmatter and a short body returns the frontmatter error, not the shrink error; a whitespace-only body returns the empty-body error; a page with an empty body accepts any non-empty body; CRLF in either body does not change the counts. [R3] [dod arm 2]
  - 4. Same file: `REFINE_MIN_BODY_RATIO` monkeypatched to 0.9 refuses a 150-character body on the 200-character page (call-time read). [R1] [dod arm 2]
  - 5. Same file: `kb_refine_page` (sync module attribute) returns an `Error:` string for the 1% body, and with `allow_shrink=True` writes it; `inspect.signature(refine_page).parameters["allow_shrink"]` is keyword-only with default `False`. [R5] [dod arm 2]
  - 6. The existing refine, review, two-phase, rollback-reporting, MCP quality and v050 tests in the DoD pass with no edit to them. [dod arm 2]
  - 7. The `kb_refine_page` entry in BACKLOG.md (`mcp/quality.py` ... accepts a body shorter than the page it replaces) is deleted; `docs/reference/mcp-servers.md` names the `allow_shrink` argument; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 250
sweep: "Ten paths: three src files, one new test file, five doc files, this card. Callers of `refine_page` in src/: `mcp/quality.py:103` only. A read-only probe over the 19 test files that call `refine_page` (595 passed, 2026-11-15) found one call under 50%, `tests/test_fixes_v050.py::test_refine_page_invalid_frontmatter`, refused earlier by the frontmatter gate, so R3's placement keeps it unchanged. No snapshot file pins the `kb_refine_page` schema."
forbid: [weakening or removing an existing refine guard, a floor that counts frontmatter characters, a shrink override without a history record, a model call or network request in tests]
non_goals: [a CLI refine command, a word- or token-based floor, guarding growth (a longer body), refusing on the ratio for pages written by ingest or compile (only `refine_page`)]
diagnosis:
  root_cause: "The only body-size checks in `refine_page` are the empty-body guard (refiner.py:224) and the MCP upper bound (`MAX_INGEST_CONTENT_CHARS`, quality.py:93). Nothing compares the new body with the current one, so one call can replace a page with 1% of it."
  same_class: "Other writers that replace a whole page body: ingest `_update_existing_page_body` merges rather than replaces, and `compile_wiki` writes from the extraction. Neither takes a caller-supplied body, so neither is in scope."
hygiene: "Run the DoD with the main checkout's `.venv` active. RED: acceptance 1, 2 and 5 fail on the unfixed code because the short body is written (or `allow_shrink` is an unexpected argument), not with an import or collection error."
doc_sync: docs/reference/mcp-servers.md
---

# T1-KBFIX-SHRINK

## Deliverable
`refine_page` refuses a replacement body under half the current body length unless the caller passes `allow_shrink=True`, and records every such override in the review history. The MCP tool exposes the same argument.

## Why
Issue #162 and the BACKLOG entry for `kb_refine_page`: the knowledge bench measured that a 1% body is accepted with no warning (`provenance.refine.accepted_1 = 1`). Owner decision 2026-11-15: 50% floor with an explicit, recorded override.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_refine_shrink_guard.py tests/test_refiner.py tests/test_review.py tests/test_cycle19_refiner_two_phase.py tests/test_cycle88_rollback_reporting.py tests/test_mcp_quality_new.py tests/test_mcp_phase2.py tests/test_fixes_v050.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED commit `c166359`, GREEN commit `612763d`. Tests: `tests/test_kbfix_refine_shrink_guard.py` (15 tests, tmp wiki and history paths, fixtures written as bytes, no model call or network).

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. 99/200 refused (error holds 200, 99, ratio; page and history bytes unchanged); 100/200 accepted | `test_a_body_just_under_half_is_refused_with_both_lengths_and_the_ratio` (exact error text `ratio 0.495 < 0.5`, pre-seeded history file byte-equal), `test_a_body_of_exactly_half_is_accepted` | pass |
| 2. 2/200 refused; written with `allow_shrink=True`, row holds `allow_shrink: true`, `previous_body_length: 200`, `new_body_length: 2`; the 100-character write's row holds none | `test_a_one_percent_body_is_refused_without_the_override`, `test_the_override_writes_the_body_and_records_it_in_history`, `test_a_write_above_the_floor_records_no_override_keys` | pass |
| 3. malformed frontmatter error wins; whitespace-only body gets the empty-body error; empty current body accepts any body; CRLF in either body does not change the counts | `test_malformed_frontmatter_is_reported_before_the_shrink_floor`, `test_a_whitespace_only_body_gets_the_empty_body_error`, `test_a_page_with_an_empty_body_accepts_any_non_empty_body`, `test_crlf_in_the_new_body_is_counted_as_one_character`, `test_crlf_in_the_current_body_is_counted_as_one_character` | pass |
| 4. ratio monkeypatched to 0.9 refuses 150/200 | `test_the_ratio_is_read_at_call_time` (exact error text `ratio 0.750 < 0.9`) | pass |
| 5. `kb_refine_page` (sync attribute) returns `Error:` for 1%, writes it with `allow_shrink=True`; `refine_page` `allow_shrink` keyword-only, default `False` | `test_the_mcp_tool_refuses_a_one_percent_body_and_writes_it_with_the_override`, `test_refine_page_takes_allow_shrink_as_keyword_only_defaulting_to_false`, `test_the_registered_mcp_tool_schema_lists_allow_shrink` (`mcp.get_tool("kb_refine_page").parameters`: boolean, default false, not required) | pass |
| 6. existing DoD test files pass with no edit | DoD arm 2; `git diff main -- tests/` touches only the new file; 150 passed, 1 skipped | pass |
| 7. BACKLOG entry deleted; `mcp-servers.md` names `allow_shrink`; one entry each in `CHANGELOG.md` `[Unreleased]` and `CHANGELOG-history.md`; State counts | `python scripts/verify_docs.py`: "docs in sync"; collected 3850 tests, 219 test files; State line reads `3850 tests across 219 test files`. BACKLOG HIGH section still holds other items, so it is not collapsed | pass (reviewer-verified) |

RED against the unfixed code (`main` at `c06d035`): 9 failed, 6 passed. 7 failures are assertions (`AssertionError` on the written short body, the missing error string, the MCP `Refined:` reply; `KeyError: 'allow_shrink'` on the signature and MCP schema). 2 are `TypeError: refine_page() got an unexpected keyword argument 'allow_shrink'` in the two tests whose subject is the argument itself (override recorded; override on a non-crossing write). The ratio test sets the attribute with `raising=False`, so it fails on the assertion rather than on the missing constant. No import or collection error. The 6 passes guard behaviour the unfixed code already met: exactly-half accepted, no override keys above the floor, malformed frontmatter error, empty-body error, empty current body, CRLF in the current body. GREEN: DoD exit 0, `150 passed, 1 skipped`.

| Input form / failure path | Covering test | Result |
|---|---|---|
| below floor (99/200, 2/200) refused | `test_a_body_just_under_half_is_refused_with_both_lengths_and_the_ratio`, `test_a_one_percent_body_is_refused_without_the_override` | pass |
| at floor (100/200) accepted | `test_a_body_of_exactly_half_is_accepted` | pass |
| above floor, with and without `allow_shrink`: no override keys | `test_a_write_above_the_floor_records_no_override_keys`, `test_allow_shrink_on_a_write_above_the_floor_records_no_override_keys` | pass |
| empty current body: no floor | `test_a_page_with_an_empty_body_accepts_any_non_empty_body` | pass |
| whitespace-only new body | `test_a_whitespace_only_body_gets_the_empty_body_error` | pass |
| malformed frontmatter with a short body | `test_malformed_frontmatter_is_reported_before_the_shrink_floor` | pass |
| CRLF in the new body / current body | `test_crlf_in_the_new_body_is_counted_as_one_character`, `test_crlf_in_the_current_body_is_counted_as_one_character` | pass |
| override crossing the floor recorded | `test_the_override_writes_the_body_and_records_it_in_history` | pass |
| monkeypatched ratio | `test_the_ratio_is_read_at_call_time` | pass |
| MCP pass-through and schema | `test_the_mcp_tool_refuses_a_one_percent_body_and_writes_it_with_the_override`, `test_the_registered_mcp_tool_schema_lists_allow_shrink` | pass |

Mutation checks (not committed; `src/kb/review/refiner.py` restored from a copy after each, `git diff --stat` showed only the candidate change):
- (a) refusal returned after the pending row is saved: 2 failed (`test_a_body_just_under_half_is_refused_with_both_lengths_and_the_ratio`, `test_a_one_percent_body_is_refused_without_the_override`), 13 passed.
- (b) override keys written on every `allow_shrink=True` call: 1 failed (`test_allow_shrink_on_a_write_above_the_floor_records_no_override_keys`), 14 passed.
- (c) `<=` instead of `<`: 4 failed (`test_a_body_of_exactly_half_is_accepted`, `test_a_write_above_the_floor_records_no_override_keys`, `test_allow_shrink_on_a_write_above_the_floor_records_no_override_keys`, `test_crlf_in_the_current_body_is_counted_as_one_character`), 11 passed.

Not done: the override is recorded in the review history only, not in the `wiki/log.md` refine line; adding it there would be an untested branch outside the acceptance list.
