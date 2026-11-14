---
id: T1-KBEVAL-HARNESS
title: "`python bench/knowledge/run.py` runs every probe under a probes directory, writes one record per probe and exits 1 when a guarded directory changes"
status: todo
branch: T1-KBEVAL-HARNESS
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-HARNESS
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/run.py
  - bench/knowledge/README.md
  - bench/knowledge/invariants.json
  - bench/knowledge/tests/conftest.py
  - bench/knowledge/tests/test_runner.py
  - .github/workflows/ci.yml
  - specs/tasks/T1-KBEVAL-HARNESS.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_runner.py -q
dod_exit: 0
requirements:
  - R1. `python bench/knowledge/run.py` shall import every `*.py` file in the probes directory (`--probes-dir`, default `bench/knowledge/probes/`) whose name does not start with `_`, in file-name order, call its `run(ctx)` and write `<out>/<probe>.json`, where `<probe>` is the file stem and `<out>` is `--out` or `_local/knowledge/`.
  - R2. Each record shall have exactly the keys `probe`, `invariants`, `commit`, `dirty` and `arms` of `specs/kb-baseline.md` (Design, Record), written as UTF-8 with sorted keys, two-space indent, `\n` line ends and no timestamp.
  - R3. `ctx` shall give a probe `tmp` (an empty directory made for that probe and removed after it), `data` (`bench/knowledge/data/<probe>/`), `wiki` and `raw` (the `--wiki` and `--raw` directories, default `demo/wiki` and `demo/raw`), `out` (the output directory) and `unmeasured(reason)`, which returns the arm `{"status": "unmeasured", "reason": reason, "cases": 0, "metrics": {}}`.
  - R4. The runner shall print one line per arm, `<probe> <arm> <status>` followed by `name=value` for each metric in name order, or by the reason for an unmeasured arm.
  - R5. WHERE `--probe <name>` is given, once or several times, the runner shall run only the named probes.
  - R6. IF a probe module has no `run`, its `run` raises, or its return value is not a mapping with `invariants` (a list of strings) and `arms` (each a mapping with `status` `measured` or `unmeasured`, an integer `cases` and a `metrics` mapping of finite numbers), THEN the runner shall print the probe name and the cause, write no record for that probe, run the remaining probes and exit 1.
  - R7. IF `--probe` names no file in the probes directory, or `--wiki`, `--raw` or `--probes-dir` is not a directory, THEN the runner shall print the cause and exit 2 before any probe runs.
  - R8. The runner shall list every file (relative path, size, modification time in nanoseconds) under the checkout's `wiki/`, `raw/` and `.data/` and under the `--wiki` and `--raw` directories before the first probe and after the last, treating a missing directory as an empty listing, and when the listings differ shall print `guarded directory changed: <path>` per difference and exit 1.
  - R9. The runner shall set `KB_PROJECT_ROOT` to a temporary directory that holds a copy of the checkout's `templates/` before any module of `kb` is imported, and shall remove that directory at exit.
  - R10. `bench/knowledge/invariants.json` shall hold I1 to I11 in order, each with `id`, `statement` and `probes`, equal in meaning to the invariant list of `specs/kb-baseline.md`.
  - R11. `.github/workflows/ci.yml` shall run `ruff check` on `bench/` as well as `src/` and `tests/`, and shall run `python -m pytest bench/knowledge/tests -q` in a step after the full suite.
  - R12. `bench/knowledge/README.md` shall state the record shape, the options, the exit codes, the guard and the steps to add a probe.
acceptance:
  - 1. `test_runner.py`, two fixture probes in a temporary probes directory: the run exits 0 and writes two records with exactly the five keys, a 40-hex `commit`, a boolean `dirty` and the arms the probes returned; a second run into another directory writes byte-equal files. [R1] [R2] [dod arm 2]
  - 2. Same file: a fixture probe sees an empty existing `tmp` that is gone after the run, `data` ending in `data/<probe>`, and `wiki`, `raw` and `out` equal to the options; `unmeasured("x")` is written with status `unmeasured`, reason `x`, `cases` 0 and empty `metrics`. [R3] [dod arm 2]
  - 3. Same file: stdout holds one line per arm in the form of R4, metrics in name order. [R4] [dod arm 2]
  - 4. Same file: `--probe a` writes only `a.json`; `--probe a --probe b` writes both. [R5] [dod arm 2]
  - 5. Same file, one test per cause (no `run`, `run` raises, return value not a mapping, a `status` outside the two values, a non-integer `cases`, a metric that is a string, a metric that is NaN): exit 1, the probe name in the output, no record for it, and the record of a second, valid probe is written. [R6] [dod arm 2]
  - 6. Same file: an unknown `--probe` name, and a file path given as `--wiki`, `--raw` and `--probes-dir` in turn, each exit 2 and write no record. [R7] [dod arm 2]
  - 7. Same file: a fixture probe that writes, deletes or rewrites a file under the `--wiki` directory makes the run exit 1 with `guarded directory changed:` and the path; a `--raw` directory with no change and a missing `.data/` give no such line. [R8] [dod arm 2]
  - 8. Same file, in a subprocess: a fixture probe that imports `kb.config` reports a `PROJECT_ROOT` outside the checkout with a `templates/` directory inside it, and that directory is gone after the run. [R9] [dod arm 2]
  - 9. Same file: `invariants.json` parses to eleven entries with ids I1 to I11 in order, non-empty statements, and `probes` drawn from `contradiction`, `retrieval`, `linker`, `citations`, `trace`, `rebuild`, `provenance`, empty for I5 and I7. [R10] [dod arm 2]
  - 10. `ci.yml` carries the two changes of R11 and no other change, and the README states the five items of R12 (reviewer-verified against the diff). [R11] [R12]
freeze: true
budget: 450
sweep: "Seven paths, six of them new. `git ls-files bench` is empty on 0b55188, so no existing file is replaced. `ci.yml` has one ruff step (`ruff check src/ tests/`) and one full-suite step (`python -m pytest -q --snapshot-warn-unused`); both are named in R11. `pyproject.toml` sets `testpaths = [\"tests\"]`, so the bench tests are not collected by the full suite and the documented test counts do not move."
forbid: [any change under src/kb/ templates/ or tests/, any change to pyproject.toml or requirements.txt, a new dependency, a timestamp or duration in a record, a model call or network request]
non_goals: [running probes in parallel (one at a time, in file-name order), probes outside the probes directory (not looked for), a probes directory with no probe file (the run prints nothing and exits 0), threshold or pass/fail judgement on a metric (the runner reports numbers only), symbolic links inside a guarded directory (listed by their own size and time, not followed)]
hygiene: "Run the DoD with the main checkout's `.venv` active; a worktree has no `.venv`. The fixture probes live in temporary directories made by the tests, so `bench/knowledge/probes/` is empty when this card merges."
---

# T1-KBEVAL-HARNESS

## Deliverable
The runner that every probe card plugs into, with the record shape, the probe entry and the exit codes frozen for the seven cards that depend on it.

## Why
Each probe card adds one module, one data directory and one test file. They can run two at a time only if none of them edits a shared registry, so the runner finds probes by listing a directory. The guard and the temporary project root are here because `kb` functions resolve `.data/` paths from `kb.config` at import, and a probe that leaks a write into the owner's corpus must fail the run, not pass it.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_runner.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence
Tests are in `bench/knowledge/tests/test_runner.py`; `T::` below abbreviates that file.

- Attempt 1 RED: `a85f23ac31e47f1c50b9b781cd0dbf625ef9fe31:bench/knowledge/tests/test_runner.py` (24 failed, 0 passed; `run.py` and `invariants.json` absent). Candidate ad57c53, blocked by R3 review (findings F1-F5).
- Attempt 2 RED: `4ff5e341d7e8c4f70188251ff920845e93df6f1c:bench/knowledge/tests/test_runner.py` (8 failed, 24 passed, 4 skipped against ad57c53's runner; each failure on its assertion). Follow-up RED `73583bf88e388f762d2e8154221ac7c0ec2e266e:bench/knowledge/tests/test_runner.py` against 3e2ef50: 2 failed (custom BaseException, stale record), 34 passed (the `_`-prefixed file and KeyboardInterrupt tests already passed), 4 skipped. The 4 skips are the symlink cases on a Windows account without the symlink privilege (WinError 1314); they run on ubuntu CI.

| Item | Proof | Result |
|---|---|---|
| 1 | `test_each_probe_gets_one_record_with_the_five_keys`, `test_record_is_sorted_two_space_json_with_lf_line_ends`, `test_two_runs_write_byte_equal_records`, `test_probes_run_in_file_name_order_not_stem_order` (F1), `test_directory_named_like_a_probe_is_not_a_probe` (F2) | pass |
| 2 | `test_ctx_gives_tmp_data_wiki_raw_out_and_unmeasured` | pass |
| 3 | `test_stdout_has_one_line_per_arm_with_metrics_in_name_order` | pass |
| 4 | `test_probe_option_runs_only_the_named_probe`, `test_probe_option_given_twice_runs_both` | pass |
| 5 | `test_invalid_probe_fails_the_run_but_others_still_write[no_run, run_raises, not_a_mapping, bad_status, cases_not_int, metric_is_string, metric_is_nan]`, `test_probe_calling_sys_exit_fails_only_that_probe[0, 3]` (F4), `test_probe_raising_a_custom_base_exception_fails_only_that_probe`, `test_failed_probe_leaves_no_record_from_an_earlier_run` | pass |
| 6 | `test_unknown_probe_name_exits_2`, `test_file_given_as_directory_option_exits_2[--wiki, --raw, --probes-dir]`, `test_directory_named_like_a_probe_is_unknown_to_probe_option` (F2) | pass |
| 7 | `test_probe_that_changes_wiki_fails_the_run[writes, deletes, rewrites]`, `test_unchanged_directories_give_no_guard_line`, `test_adding_or_removing_a_link_under_wiki_fails_the_run[*]` (F3), `test_unlistable_guarded_directory_fails_the_run` (F5) | pass (symlink cases skip on Windows without privilege) |
| 8 | `test_kb_config_sees_a_temporary_root_with_templates` (every subprocess test runs the runner in a fresh interpreter) | pass |
| 9 | `test_invariants_json_lists_i1_to_i11_with_their_probes` | pass |
| 10 | Reviewer: `git diff main -- .github/workflows/ci.yml` has two hunks, `@@ -97,7` (`ruff check src/ tests/ bench/`) and `@@ -125,6` (step "Knowledge bench runner tests" after the full suite). README sections: "Record" (shape), "Options", "Exit codes", "Guard", "Add a probe". | reviewer-verified |

Input forms and failure paths handled by the attempt-2 repair hunks:

| Form or path | Behaviour | Test |
|---|---|---|
| regular `*.py` file in probes dir | a probe, run in full file-name order | `T::test_probes_run_in_file_name_order_not_stem_order` |
| `a.py` and `a.b.py`, with and without `--probe` | `a.b.py` runs first in both | `T::test_probes_run_in_file_name_order_not_stem_order` |
| `_`-prefixed file | not a probe; `--probe _helper` exits 2 | `T::test_underscore_file_is_not_a_probe` |
| directory named `helper.py` | not a probe: empty run exits 0, prints nothing | `T::test_directory_named_like_a_probe_is_not_a_probe` |
| `--probe helper` when only `helper.py/` exists | unknown probe, exit 2 | `T::test_directory_named_like_a_probe_is_unknown_to_probe_option` |
| file link under `--wiki`, created or removed | listed by lstat, change reported | `T::test_adding_or_removing_a_link_under_wiki_fails_the_run[file_symlink-*]` (ubuntu CI; skips here) |
| directory link under `--wiki`, created or removed | listed by lstat, not traversed, change reported | `T::test_adding_or_removing_a_link_under_wiki_fails_the_run[dir_symlink-*]` (ubuntu CI; skips here) |
| Windows junction under `--wiki`, created or removed | treated as a link: listed by lstat, not traversed | `T::test_adding_or_removing_a_link_under_wiki_fails_the_run[junction-*]` (Windows only) |
| missing guarded dir (checkout `.data/`) | lists as empty, no guard line | `T::test_probe_that_changes_wiki_fails_the_run[*]`, `T::test_unchanged_directories_give_no_guard_line` |
| guarded subtree that cannot be listed | `cannot list guarded directory: <path>: <cause>`, exit 1 | `T::test_unlistable_guarded_directory_fails_the_run` (in-process, `os.scandir` raises PermissionError) |
| probe calls `sys.exit(0)` after writing under `--wiki` | probe failure, next probe's record written, guard line printed, exit 1 | `T::test_probe_calling_sys_exit_fails_only_that_probe[0]` |
| probe calls `sys.exit(3)` | probe failure, next probe's record written, exit 1 | `T::test_probe_calling_sys_exit_fails_only_that_probe[3]` |
| custom `BaseException` subclass raised after writing under `--wiki` | probe failure, next probe's record written, guard line printed, exit 1 | `T::test_probe_raising_a_custom_base_exception_fails_only_that_probe` |
| failing probe with a record from an earlier run in `--out` | old record deleted before the probe runs, exit 1 | `T::test_failed_probe_leaves_no_record_from_an_earlier_run` |
| `KeyboardInterrupt` in a probe | propagates out of `main()`; `KB_PROJECT_ROOT` restored to its previous value | `T::test_keyboard_interrupt_propagates_and_restores_kb_project_root` (in-process) |

Note: `bench/knowledge/probes/` does not exist until the first probe card adds a file (git does not keep an empty directory and no placeholder is in `allow_paths`), so a bare `python bench/knowledge/run.py` exits 2 per R7 until then.
