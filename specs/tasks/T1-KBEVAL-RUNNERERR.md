---
id: T1-KBEVAL-RUNNERERR
title: "The knowledge-bench runner reports its six error paths with a defined exit code and never lets a probe write inside an input directory (#148)"
status: todo
branch: T1-KBEVAL-RUNNERERR
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-RUNNERERR
plan_ref: plans/kb-fixes-2.md#order-of-work
allow_paths:
  - bench/knowledge/run.py
  - bench/knowledge/tests/test_runner.py
  - bench/knowledge/README.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - specs/tasks/T1-KBEVAL-RUNNERERR.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_runner.py -q
dod_exit: 0
requirements:
  - R1. IF the probes directory cannot be listed, THEN the runner shall name the directory and the cause on stderr and exit 2 before any probe runs.
  - R2. WHEN a run starts, the runner shall remove `<out>/<probe>.json` of every selected probe before the first probe runs, a read-only record included, or name the path and the cause and exit 1 before any probe runs.
  - R3. WHEN a probe fails, the runner shall remove that probe's record, a read-only one included, or name on stderr the path of a record it cannot remove.
  - R4. WHEN a probe fails, the runner shall set the exit code to 1 before writing any diagnostic, so that a diagnostic that cannot be written stops neither the later probes nor the guard comparison.
  - R5. WHEN stdout's pipe is closed during a run, the process shall exit with the run's exit code, not 120.
  - R6. IF `--out` cannot be created or is not a directory, THEN the runner shall name it and the cause on stderr and exit 2 before any probe runs.
  - R7. IF the resolved `--out` equals or lies inside the resolved `--wiki`, `--raw`, or the checkout's `wiki/`, `raw/` or `.data/`, THEN the runner shall exit 2 naming both paths, before any probe runs and before any directory is created.
acceptance:
  - 1. `test_runner.py`: with the probes directory's listing raising `PermissionError`, the run exits 2, stderr names the directory, and no probe runs; an empty readable probes directory exits as it does today. [R1] [dod arm 2]
  - 2. Same file: a read-only stale record of a selected probe is gone before that probe runs (the probe observes it absent); with record removal failing, the run exits 1 naming the path and no probe runs; the record of an unselected probe is left alone. [R2] [dod arm 2]
  - 3. Same file: a probe that writes its own record read-only and then raises leaves no record after the run; with that removal failing, stderr names the path and the exit code is 1. [R3] [dod arm 2]
  - 4. Same file, a real subprocess whose stdout and stderr share one pipe the parent closes before the run: a failing first probe does not stop the second probe from writing its record, the guard comparison runs, and the exit code is 1, not 120. [R4] [R5] [dod arm 2]
  - 5. Same file: `--out` naming an existing file, and `--out` whose creation raises `PermissionError`, each exit 2 naming the path, with no probe run and no traceback on stderr. [R6] [dod arm 2]
  - 6. Same file: `--out` equal to `--wiki`, `--out` inside `--raw`, and `--out` inside the checkout's `.data/` each exit 2 naming both paths, and the `--out` path does not exist afterwards; an `--out` that reaches `--wiki` through a symlink exits 2 the same way (skipped, with the reason, where the OS refuses to create the symlink). [R7] [dod arm 2]
  - 7. Every existing test in `test_runner.py` passes with no existing test edited; `bench/knowledge/README.md` states the new usage errors (exit 2) and the record clean-up (exit 1); `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id (reviewer-verified). [dod arm 2]
depends_on: []
budget: 450
sweep: "Six paths: the runner, its test file, the bench README, two changelogs and this card. The six items are #148 items 1-4 (R3 of T1-KBEVAL-HARNESS-2, verdict `.review/T1-KBEVAL-HARNESS-2.r3.1.531f671d.json`), item 5 (R3 of T1-KBEVAL-HARNESS-3, `.review/T1-KBEVAL-HARNESS-3.r3.1.ff0e78e2.json`) and item 6 (R3 decision 4 of T1-KBEVAL-TRACE, findings F17 and F18). Probe modules are not changed: R7 protects every probe at the runner."
forbid: [removing records of unselected probes, deleting anything inside `--wiki`, `--raw`, `wiki/`, `raw/` or `.data/`, swallowing an error without a stderr line, editing an existing test, a model call or network request in tests]
non_goals: [validating `--probes-dir` overlap with the inputs (it is read only), Windows ACL-based read-only directories (only the read-only file attribute), retrying a failed removal]
diagnosis:
  root_cause: "The runner was written for healthy streams and directories: `Path.glob` suppresses listing errors, `discard_record` swallows a failed removal, the failure handler prints before it records the failure, `main()` restores stream settings on a broken stdout, `out.mkdir` runs outside the usage checks, and no check relates `--out` to the input directories."
  same_class: "`guarded_listing` already raises and reports listing errors (the model for R1); `write_record` already encodes before writing. No other runner path writes outside `--out` or the per-probe temporary directory."
hygiene: "Run the DoD with the main checkout's `.venv` active. Read-only on Windows means the file attribute: clear it with `os.chmod(path, stat.S_IWRITE)` before `unlink`. The closed-pipe test must run on ubuntu CI; on Windows it may skip only if the OS reports no error for a write to a closed pipe, and the skip reason says so."
---

# T1-KBEVAL-RUNNERERR

## Deliverable
`bench/knowledge/run.py` fails cleanly on an unreadable probes directory, an unremovable or read-only record, a closed output pipe, and a bad or overlapping `--out`, each with a stderr line naming the path and an exit code from the documented set.

## Why
Issue #148 (six advisory findings across three R3 reviews): each path either ends the run with a traceback or exit 120, hides a failure, or, for item 6, lets the trace probe write or delete `trace-sample.jsonl` inside a protected input directory.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_runner.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

### Attempt 1 (implementer, 2026-11-16)
- Base: `origin/main` f8e217e. Commits: 44f3aad (RED tests only), 3c6b53e (runner), a57e386 (README, changelogs), then this evidence commit.
- Environment: Windows 11, Python 3.13.13, main checkout `.venv` (CI runs Python 3.12 on ubuntu-latest).
- RED (44f3aad tests against the unchanged runner): `python -m pytest bench/knowledge/tests/test_runner.py -q -rfs --tb=line` exit 1, `17 failed, 42 passed, 5 skipped` (output sha256 afba92da...). Each new test failed on its behaviour:
  - `test_unlistable_probes_directory_exits_2_naming_it`: exit 0 with empty stderr (`Path.glob` read the denied directory as empty).
  - `test_stale_records_of_selected_probes_are_gone_before_the_first_probe`: `a_looker failed: PermissionError: [WinError 5]` on its read-only stale record; exit 1.
  - `test_stale_record_that_cannot_be_removed_exits_1_before_any_probe`: probe `a` ran before `b.json` was tried (marker present).
  - `test_failed_probe_leaves_no_read_only_record_of_its_own`: the read-only record survived (`assert not True`).
  - `test_failed_probe_record_that_cannot_be_removed_is_named_on_stderr`: no stderr line names `a.json`.
  - three `test_closed_output_pipe_*`: `assert 120 == 1`.
  - `test_unwritable_diagnostic_stops_neither_later_probes_nor_the_guard`: `BrokenPipeError` escaped `main()` from the failure diagnostic.
  - `test_out_naming_an_existing_file_exits_2`: exit 1 with a `FileExistsError` traceback.
  - `test_out_that_cannot_be_created_exits_2`: `PermissionError` escaped `main()` from `out.mkdir`.
  - `test_out_equal_to_wiki_exits_2_naming_both`, `test_out_inside_raw_exits_2_and_is_not_created`, the three `test_out_inside_a_checkout_input_directory_*` cases and `test_out_reaching_wiki_through_a_link_exits_2[junction]`: exit 1 with `guarded directory changed: <input>/.../a.json`, so the probe had written into the input directory. The checkout cases removed the directories the old runner created; `wiki/`, `raw/` and `.data/` did not exist in the worktree before or after.
  - `test_empty_readable_probes_directory_exits_0_with_no_output` passed (control: current behaviour kept).
- DoD (exact command, worktree root, main checkout `.venv` first on PATH): `ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_runner.py -q` exit 0, output sha256 329672cd...:
  ```
  All checks passed!
  ...........................ssss...............................s.         [100%]
  59 passed, 5 skipped in 13.31s
  ```
- Bench tests: `python -m pytest bench/knowledge/tests -q` exit 0, `413 passed, 5 skipped`. `ruff format --check bench/knowledge`: 18 files already formatted.
- Runner smoke: `python bench/knowledge/run.py --out <scratchpad>/smoke-a57e386` (outside the repo) exit 0; seven records (`citations`, `contradiction`, `linker`, `provenance`, `rebuild`, `retrieval`, `trace`) plus `trace-sample.jsonl`; no guard line.
- `git diff --numstat origin/main...a57e386`:
  ```
  10   0   CHANGELOG-history.md
  1    0   CHANGELOG.md
  5    3   bench/knowledge/README.md
  134  23  bench/knowledge/run.py
  365  1   bench/knowledge/tests/test_runner.py
  ```
  Non-test lines 176; test lines 366; total 542 against `budget: 450`. Over the budget by the test file; no existing test edited.
- Skips (5, all `require_link_kind`: "symlink creation needs a privilege this Windows account lacks", WinError 1314): four existing `test_adding_or_removing_a_link_under_wiki_fails_the_run` symlink cases and the new `test_out_reaching_wiki_through_a_link_exits_2[dir_symlink]`. The junction case of the new test ran and passed. The closed-pipe tests ran on Windows (a write to a closed pipe raises `OSError(22)` there); they skip only where a write to a closed pipe raises nothing.

| # | Requirement | Test(s) in `test_runner.py` | Result |
|---|---|---|---|
| 1 | R1 | `test_unlistable_probes_directory_exits_2_naming_it`, `test_empty_readable_probes_directory_exits_0_with_no_output` | pass |
| 2 | R2 | `test_stale_records_of_selected_probes_are_gone_before_the_first_probe` (read-only, observed absent by the first probe, unselected kept), `test_stale_record_that_cannot_be_removed_exits_1_before_any_probe` | pass |
| 3 | R3 | `test_failed_probe_leaves_no_read_only_record_of_its_own`, `test_failed_probe_record_that_cannot_be_removed_is_named_on_stderr` | pass |
| 4 | R4, R5 | `test_closed_output_pipe_keeps_later_probes_and_exit_code_1`, `test_closed_output_pipe_with_a_guard_change_exits_1_not_120`, `test_closed_output_pipe_with_summary_lines_exits_1_not_120` (real subprocess, stdout and stderr on one pipe closed before the run), `test_unwritable_diagnostic_stops_neither_later_probes_nor_the_guard` (in-process: the guard line is still attempted) | pass |
| 5 | R6 | `test_out_naming_an_existing_file_exits_2`, `test_out_that_cannot_be_created_exits_2` | pass |
| 6 | R7 | `test_out_equal_to_wiki_exits_2_naming_both`, `test_out_inside_raw_exits_2_and_is_not_created`, `test_out_inside_a_checkout_input_directory_exits_2_and_is_not_created[wiki,raw,.data]`, `test_out_reaching_wiki_through_a_link_exits_2[dir_symlink,junction]` | pass (dir_symlink skipped on this account, see above) |
| 7 | existing tests, docs | all 45 earlier cases pass unedited; README exit codes 1 and 2 plus the record clean-up paragraph; one entry each in `CHANGELOG.md` [Unreleased] and `CHANGELOG-history.md` | pass (reviewer-verified item) |
