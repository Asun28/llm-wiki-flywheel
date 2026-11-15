---
id: T1-KBFIX-SHRINK-2
title: "`refine_page` refuses a new body under half the current body unless `allow_shrink=True`, which the review history records; `kb_refine_page` passes the flag through (#162)"
status: todo
branch: T1-KBFIX-SHRINK-2
worktree: D:\wt\llm-wiki-flywheel\T1-KBFIX-SHRINK-2
plan_ref: plans/kb-defects-1.md#order-of-work
allow_paths:
  - src/kb/review/refiner.py
  - src/kb/mcp/quality.py
  - src/kb/config.py
  - tests/test_kbfix_refine_shrink_guard.py
  - tests/test_workflow_e2e.py
  - BACKLOG.md
  - docs/reference/mcp-servers.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T1-KBFIX-SHRINK.md
  - specs/tasks/T1-KBFIX-SHRINK-2.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_refine_shrink_guard.py tests/test_refiner.py tests/test_review.py tests/test_cycle19_refiner_two_phase.py tests/test_cycle88_rollback_reporting.py tests/test_mcp_quality_new.py tests/test_mcp_phase2.py tests/test_fixes_v050.py tests/test_workflow_e2e.py -q
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
  - 6. The existing refine, review, two-phase, rollback-reporting, MCP quality, v050 and workflow-e2e tests in the DoD pass. The only edit to an existing test is the one the floor forces: `tests/test_workflow_e2e.py::test_e2e_ingest_refine_requery` replaces a whole generated entity page with a short marker on purpose, so its `refine_page` call passes `allow_shrink=True`; none of its assertions change. [dod arm 2]
  - 7. The `kb_refine_page` entry in BACKLOG.md (`mcp/quality.py` ... accepts a body shorter than the page it replaces) is deleted and its open truncation half is re-filed as its own entry; `docs/reference/mcp-servers.md` names the `allow_shrink` argument; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry for this fix (under T1-KBFIX-SHRINK, the card this one continues, naming this card too); the counts in the `State` line of `CLAUDE.md` equal the collected test count and test-file count on the candidate (reviewer-verified).
depends_on: []
budget: 250
sweep: "Twelve paths: three src files, one new and one existing test file, five doc files, this card and its predecessor's card (which holds attempts 1-2 evidence on the branch this card continues). Callers of `refine_page` in src/: `mcp/quality.py:103` only. A read-only probe over the 19 test files that call `refine_page` found one call under 50%, refused earlier by the frontmatter gate; it missed `tests/test_workflow_e2e.py::test_e2e_ingest_refine_requery` (47 of 242 characters), which CI run 43695280342 on candidate e5f967b found (1 failed, 3811 passed). No snapshot file pins the `kb_refine_page` schema."
forbid: [weakening or removing an existing refine guard, a floor that counts frontmatter characters, a shrink override without a history record, an edit to an existing test other than the `allow_shrink=True` argument of acceptance 6, a model call or network request in tests]
non_goals: [a CLI refine command, a word- or token-based floor, guarding growth (a longer body), refusing on the ratio for pages written by ingest or compile (only `refine_page`)]
diagnosis:
  root_cause: "The only body-size checks in `refine_page` are the empty-body guard (refiner.py:224) and the MCP upper bound (`MAX_INGEST_CONTENT_CHARS`, quality.py:93). Nothing compares the new body with the current one, so one call can replace a page with 1% of it."
  same_class: "Other writers that replace a whole page body: ingest `_update_existing_page_body` merges rather than replaces, and `compile_wiki` writes from the extraction. Neither takes a caller-supplied body, so neither is in scope."
hygiene: "Run the DoD with the main checkout's `.venv` active. The branch continues T1-KBFIX-SHRINK at e5f967b, then a merge-based sync with main; never rebase. RED for the e2e edit: on e5f967b the e2e test fails on its `refine_page failed` assertion (CI run 43695280342)."
doc_sync: docs/reference/mcp-servers.md
---

# T1-KBFIX-SHRINK-2

## Deliverable
`refine_page` refuses a replacement body under half the current body length unless the caller passes `allow_shrink=True`, and records every such override in the review history. The MCP tool exposes the same argument.

## Why
Issue #162 and the BACKLOG entry for `kb_refine_page`: the knowledge bench measured that a 1% body is accepted with no warning (`provenance.refine.accepted_1 = 1`). Owner decision 2026-11-15: 50% floor with an explicit, recorded override.

## Successor
Successor of T1-KBFIX-SHRINK (goal g-20261115060441-b905b2, owner-authorised resume 2026-11-15). That card passed R3 decision 2 and the second pass at candidate e5f967b, then stopped on CI at PR #170: the new floor refuses `tests/test_workflow_e2e.py::test_e2e_ingest_refine_requery`, which replaces a whole 242-character entity page with a 47-character marker (CI run 43695280342: 1 failed, 3811 passed, 20 skipped). A card stopped for CI is not re-admitted, so this card carries the same contract, continues from that branch, passes `allow_shrink=True` in that one test call, and supersedes PR #170. Attempts 1-2 evidence stays in `specs/tasks/T1-KBFIX-SHRINK.md` on the branch.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_refine_shrink_guard.py tests/test_refiner.py tests/test_review.py tests/test_cycle19_refiner_two_phase.py tests/test_cycle88_rollback_reporting.py tests/test_mcp_quality_new.py tests/test_mcp_phase2.py tests/test_fixes_v050.py tests/test_workflow_e2e.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
