---
id: T1-KBEVAL-RUNNERERR-2
title: "The knowledge-bench runner reports its six error paths with a defined exit code and never lets a probe write inside an input directory (#148)"
status: merged
branch: T1-KBEVAL-RUNNERERR-2
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-RUNNERERR-2
plan_ref: plans/kb-fixes-2.md#order-of-work
allow_paths:
  - bench/knowledge/run.py
  - bench/knowledge/tests/test_runner.py
  - bench/knowledge/README.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - specs/tasks/T1-KBEVAL-RUNNERERR.md
  - specs/tasks/T1-KBEVAL-RUNNERERR-2.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_runner.py -q
dod_exit: 0
requirements:
  - R1. IF the probes directory cannot be inspected or listed (an error from `stat`, `is_dir` or the listing included), THEN the runner shall name the directory and the cause on stderr and exit 2 before any probe runs.
  - R2. WHEN a run starts, the runner shall remove `<out>/<probe>.json` of every selected probe before the first probe runs, a read-only record included, or name the path and the cause and exit 1 before any probe runs.
  - R3. WHEN a probe fails, the runner shall remove that probe's record, a read-only one included, or name on stderr the path of a record it cannot remove.
  - R4. WHEN a probe fails, the runner shall set the exit code to 1 before writing any diagnostic, so that a diagnostic that cannot be written stops neither the later probes nor the guard comparison.
  - R5. WHEN stdout's pipe is closed during a run, the process shall exit with the run's exit code, not 120.
  - R6. IF `--out` cannot be inspected or created or is not a directory (an error from `stat`, `exists`, `is_dir` or `mkdir` included), THEN the runner shall name it and the cause on stderr and exit 2 before any probe runs.
  - R7. IF the resolved `--out` equals or lies inside the resolved `--wiki`, `--raw`, or the checkout's `wiki/`, `raw/` or `.data/`, THEN the runner shall exit 2 naming both paths, before any probe runs and before any directory is created.
acceptance:
  - 1. `test_runner.py`: with the probes directory's listing raising `PermissionError`, the run exits 2, stderr names the directory, and no probe runs; an empty readable probes directory exits as it does today; with the probes directory's `stat` (the `is_dir` check) raising `PermissionError`, as for a directory under an unreadable POSIX parent, the run also exits 2 naming the directory, with no traceback. [R1] [dod arm 2]
  - 2. Same file: a read-only stale record of a selected probe is gone before that probe runs (the probe observes it absent); with record removal failing, the run exits 1 naming the path and no probe runs; the record of an unselected probe is left alone. [R2] [dod arm 2]
  - 3. Same file: a probe that writes its own record read-only and then raises leaves no record after the run; with that removal failing, stderr names the path and the exit code is 1. [R3] [dod arm 2]
  - 4. Same file, a real subprocess whose stdout and stderr share one pipe the parent closes before the run: a failing first probe does not stop the second probe from writing its record, the guard comparison runs, and the exit code is 1, not 120. [R4] [R5] [dod arm 2]
  - 5. Same file: `--out` naming an existing file, and `--out` whose creation raises `PermissionError`, each exit 2 naming the path, with no probe run and no traceback on stderr; so does an `--out` whose `stat` (the `exists` / `is_dir` checks) raises `PermissionError`. [R6] [dod arm 2]
  - 6. Same file: `--out` equal to `--wiki`, `--out` inside `--raw`, and `--out` inside the checkout's `wiki/`, `raw/` and `.data/` each exit 2 naming both paths, and the `--out` path does not exist afterwards; the checkout cases run against a temporary checkout the test points the runner's checkout path at, and no test creates, changes or deletes anything under the real checkout's `wiki/`, `raw/` or `.data/`; an `--out` that reaches `--wiki` through a symlink exits 2 the same way (skipped, with the reason, where the OS refuses to create the symlink). [R7] [dod arm 2]
  - 7. Every existing test in `test_runner.py` passes with no existing test edited; `bench/knowledge/README.md` states the new usage errors (exit 2) and the record clean-up (exit 1); `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry for this fix (under T1-KBEVAL-RUNNERERR, naming its successor, this card) (reviewer-verified). [dod arm 2]
depends_on: []
budget: 450
sweep: "Seven paths: the runner, its test file, the bench README, two changelogs, this card and its predecessor's card (which holds attempt 1 evidence on the branch this card continues). The six items are #148 items 1-4 (R3 of T1-KBEVAL-HARNESS-2, verdict `.review/T1-KBEVAL-HARNESS-2.r3.1.531f671d.json`), item 5 (R3 of T1-KBEVAL-HARNESS-3, `.review/T1-KBEVAL-HARNESS-3.r3.1.ff0e78e2.json`) and item 6 (R3 decision 4 of T1-KBEVAL-TRACE, findings F17 and F18). Probe modules are not changed: R7 protects every probe at the runner."
forbid: [removing records of unselected probes, deleting anything inside `--wiki`, `--raw`, `wiki/`, `raw/` or `.data/` (in the runner and in its tests), a test that creates or deletes anything under the real checkout's `wiki/`, `raw/` or `.data/`, swallowing an error without a stderr line, editing an existing test, a model call or network request in tests]
non_goals: [validating `--probes-dir` overlap with the inputs (it is read only), Windows ACL-based read-only directories (only the read-only file attribute), retrying a failed removal]
diagnosis:
  root_cause: "The runner was written for healthy streams and directories: `Path.glob` suppresses listing errors, `discard_record` swallows a failed removal, the failure handler prints before it records the failure, `main()` restores stream settings on a broken stdout, `out.mkdir` runs outside the usage checks, and no check relates `--out` to the input directories."
  same_class: "`guarded_listing` already raises and reports listing errors (the model for R1); `write_record` already encodes before writing. No other runner path writes outside `--out` or the per-probe temporary directory."
hygiene: "Run the DoD with the main checkout's `.venv` active. Read-only on Windows means the file attribute: clear it with `os.chmod(path, stat.S_IWRITE)` before `unlink`. The closed-pipe test must run on ubuntu CI; on Windows it may skip only if the OS reports no error for a write to a closed pipe, and the skip reason says so."
---

# T1-KBEVAL-RUNNERERR-2

## Deliverable
`bench/knowledge/run.py` fails cleanly on an unreadable probes directory, an unremovable or read-only record, a closed output pipe, and a bad or overlapping `--out`, each with a stderr line naming the path and an exit code from the documented set.

## Why
Issue #148 (six advisory findings across three R3 reviews): each path either ends the run with a traceback or exit 120, hides a failure, or, for item 6, lets the trace probe write or delete `trace-sample.jsonl` inside a protected input directory.

## Successor
Successor of T1-KBEVAL-RUNNERERR (goal g-20261115184928-6896e7, owner-authorised 2026-11-16). R3 decision 1 on candidate `976e0ab` (verdict `T1-KBEVAL-RUNNERERR.r3.1.93d8d46e`) raised three findings the loop records as advisory, so that card could only ship the candidate as it stood: (P1, class `protected-input-test-deletion`) the overlap test's failure cleanup deleted inside the real checkout's `wiki/`, `raw/` or `.data/`, and did so in the RED run; (P2 x2, class `unguarded-directory-preflight`) on POSIX a `--probes-dir` or `--out` under an inaccessible parent raises `PermissionError` from `is_dir()` / `exists()` before the new handlers, so R1 and R6 ended in a traceback there. This card carries the contract with R1, R6, acceptance 1, 5 and 6 and the forbid list amended for them, continues from that branch, and gets its own R3. Attempt 1 evidence stays in `specs/tasks/T1-KBEVAL-RUNNERERR.md` on the branch.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_runner.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

### Attempt 1 (implementer, 2026-11-16)
- Origin: T1-KBEVAL-RUNNERERR candidate `976e0ab` (its attempt 1 evidence stays in `specs/tasks/T1-KBEVAL-RUNNERERR.md`), merge of origin/main `efd3f35`. Commits: ef6e423 (RED tests), 880a6af (runner), 5143902 (README, changelogs), then this evidence commit.
- Environment: Windows 11, Python 3.13.13, main checkout `.venv` (CI: Python 3.12, ubuntu-latest).
- Findings repaired: P1 `protected-input-test-deletion` (the checkout overlap test now runs in-process with `runner.CHECKOUT` pointed at `<tmp>/checkout` and `runner.git_state` fixed at the git boundary; the cleanup that targeted the real checkout and the `shutil` import are removed); P2 `unguarded-directory-preflight` at `run.py:328` and `run.py:350` (new `stat_mode`, `resolved`, `prepare_out` raise `UsageError`; `run_all` reports it and exits 2).
- Same class, checked: the `--wiki` / `--raw` `is_dir` checks (same loop as `--probes-dir`, fixed and tested); `resolve()` of `--wiki`, `--raw`, `--out` and of the checkout's `wiki/`, `raw/`, `.data/` for the overlap check (raised at `run.py:331`; fixed, the three option cases tested). Found and NOT changed, outside R1/R6/R7: after the preflight, `(CHECKOUT / "templates").is_dir()` + `shutil.copytree` and `tempfile.mkdtemp` can still raise out of `main()` with a traceback; they concern the checkout's `templates/` and the system temp directory, not an option path.
- RED (ef6e423 tests against the `976e0ab` runner): `python -m pytest bench/knowledge/tests/test_runner.py -q -rfs --tb=line` exit 1, `7 failed, 62 passed, 5 skipped` (output sha256 5942b678...). Each failure is `PermissionError` escaping `main()` from the preflight: `run.py:328` (`is_dir`) for `test_probes_directory_that_cannot_be_inspected_exits_2` and `test_input_directory_that_cannot_be_inspected_exits_2[--wiki,--raw]`; `run.py:331` (`resolve`) for `test_option_path_that_cannot_be_resolved_exits_2[--wiki,--raw,--out]`; `run.py:350` (`exists`) for `test_out_that_cannot_be_inspected_exits_2`. The six rewritten `test_out_inside_a_checkout_input_directory_exits_2_and_is_not_created[<dir>-present|absent]` cases passed at RED: the `976e0ab` runner already had the R7 check, the change there is test isolation (P1), and with `git_state` fixed a runner without the check would reach `mkdir` and run the marker probe, so the case still discriminates.
- DoD (exact command, worktree root, main checkout `.venv` first on PATH): `ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_runner.py -q` exit 0, output sha256 69938b9d...:
  ```
  All checks passed!
  ...........................ssss......................................... [ 97%]
  s.                                                                       [100%]
  69 passed, 5 skipped in 21.11s
  ```
- Bench tests: `python -m pytest bench/knowledge/tests -q` exit 0, `423 passed, 5 skipped`. `ruff format --check bench/knowledge`: 18 files already formatted.
- Runner smoke: `python bench/knowledge/run.py --out <scratchpad>/smoke-runnererr2` (outside the repo) exit 0; seven records plus `trace-sample.jsonl`; no guard line. The worktree's `wiki/`, `raw/` and `.data/` did not exist before or after any run, RED included.
- `git diff --numstat 976e0ab..5143902` (this card): `CHANGELOG-history.md` 5/3, `CHANGELOG.md` 1/1, `bench/knowledge/README.md` 1/1, `bench/knowledge/run.py` 70/36, `bench/knowledge/tests/test_runner.py` 104/15.
- `git diff --numstat origin/main...5143902` (whole branch): `CHANGELOG-history.md` 12/0, `CHANGELOG.md` 1/0, `bench/knowledge/README.md` 5/3, `bench/knowledge/run.py` 177/32, `bench/knowledge/tests/test_runner.py` 454/1, `specs/tasks/T1-KBEVAL-RUNNERERR.md` 46/0. Non-test lines 230; test lines 455.
- Skips (5, all `require_link_kind`: "symlink creation needs a privilege this Windows account lacks", WinError 1314): four existing `test_adding_or_removing_a_link_under_wiki_fails_the_run` symlink cases and `test_out_reaching_wiki_through_a_link_exits_2[dir_symlink]`. The junction case ran and passed. The closed-pipe tests ran (Windows raises `OSError(22)` on a write to a closed pipe).

| # | Requirement | Test(s) in `test_runner.py` | Result |
|---|---|---|---|
| 1 | R1 | `test_unlistable_probes_directory_exits_2_naming_it`, `test_empty_readable_probes_directory_exits_0_with_no_output`, `test_probes_directory_that_cannot_be_inspected_exits_2` (new: `os.stat` raising) | pass |
| 2 | R2 | `test_stale_records_of_selected_probes_are_gone_before_the_first_probe`, `test_stale_record_that_cannot_be_removed_exits_1_before_any_probe` | pass |
| 3 | R3 | `test_failed_probe_leaves_no_read_only_record_of_its_own`, `test_failed_probe_record_that_cannot_be_removed_is_named_on_stderr` | pass |
| 4 | R4, R5 | three `test_closed_output_pipe_*` (real subprocess, one shared pipe closed before the run), `test_unwritable_diagnostic_stops_neither_later_probes_nor_the_guard` | pass |
| 5 | R6 | `test_out_naming_an_existing_file_exits_2`, `test_out_that_cannot_be_created_exits_2`, `test_out_that_cannot_be_inspected_exits_2` (new: `os.stat` raising before `mkdir`) | pass |
| 6 | R7 | `test_out_equal_to_wiki_exits_2_naming_both`, `test_out_inside_raw_exits_2_and_is_not_created`, `test_out_inside_a_checkout_input_directory_exits_2_and_is_not_created[wiki,raw,.data x present,absent]` (temporary checkout), `test_out_reaching_wiki_through_a_link_exits_2[dir_symlink,junction]` | pass (dir_symlink skipped here) |
| 7 | existing tests, docs | 45 earlier cases pass unedited; README exit code 2 adds `cannot inspect` / `cannot resolve`; the T1-KBEVAL-RUNNERERR entries in `CHANGELOG.md` and `CHANGELOG-history.md` name this successor | pass (reviewer-verified item) |
| - | same class | `test_input_directory_that_cannot_be_inspected_exits_2[--wiki,--raw]`, `test_option_path_that_cannot_be_resolved_exits_2[--wiki,--raw,--out]` | pass |
