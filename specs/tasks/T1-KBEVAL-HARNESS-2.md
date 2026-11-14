---
id: T1-KBEVAL-HARNESS-2
title: "`python bench/knowledge/run.py` runs every probe under a probes directory, writes one record per probe and exits 1 when a guarded directory changes"
status: todo
branch: T1-KBEVAL-HARNESS-2
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-HARNESS-2
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/run.py
  - bench/knowledge/README.md
  - bench/knowledge/invariants.json
  - bench/knowledge/tests/conftest.py
  - bench/knowledge/tests/test_runner.py
  - .github/workflows/ci.yml
  - specs/tasks/T1-KBEVAL-HARNESS.md
  - specs/tasks/T1-KBEVAL-HARNESS-2.md
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
  - R13. IF writing a probe's record or printing its summary lines fails, including a string UTF-8 cannot encode and a console whose encoding cannot show a character, THEN the runner shall treat it as that probe's failure under R6, leave no record for that probe, and still run the remaining probes and the R8 comparison.
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
  - 11. Same file, one test per cause: a fixture probe whose unmeasured reason holds a lone surrogate, and a run in a subprocess whose stdout encoding is cp1252 given a probe whose reason is Chinese text: each run exits 1 with the probe name in the output and no traceback, leaves no record for that probe, writes the record of a second, valid probe, and prints `guarded directory changed:` when that probe also wrote under `--wiki`. [R13] [dod arm 2]
freeze: true
budget: 1300
sweep: "Successor of T1-KBEVAL-HARNESS, continued from its branch (candidate 009f188: runner, tests, README, invariants, CI step). `git ls-files bench` is empty on e79a097, so no existing file on main is replaced. `ci.yml` on e79a097 has one ruff step (`ruff check src/ tests/`), the collection step with `--snapshot-warn-unused` from #146, and one full-suite step; R11 touches the first and adds a step after the last. `pyproject.toml` sets `testpaths = [\"tests\"]`, so the bench tests are not collected by the full suite."
forbid: [any change under src/kb/ templates/ or tests/, any change to pyproject.toml or requirements.txt, a new dependency, a timestamp or duration in a record, a model call or network request]
non_goals: [running probes in parallel (one at a time, in file-name order), probes outside the probes directory (not looked for), a probes directory with no probe file (the run prints nothing and exits 0), threshold or pass/fail judgement on a metric (the runner reports numbers only), symbolic links and junctions inside a guarded directory (listed by their own size and time, not followed), a probe that raises KeyboardInterrupt (it stops the run as Ctrl-C does; the runner cannot tell the two apart, so it restores KB_PROJECT_ROOT and re-raises)]
hygiene: "Run the DoD with the main checkout's `.venv/Scripts` first on PATH; a worktree has no `.venv` and the venv's `activate` script points at a stale path. The fixture probes live in temporary directories made by the tests, so `bench/knowledge/probes/` is empty when this card merges."
---

# T1-KBEVAL-HARNESS-2

## Deliverable
The runner that every probe card plugs into, with the record shape, the probe entry and the exit codes frozen for the seven cards that depend on it.

## Why
Successor of T1-KBEVAL-HARNESS (goal g-20261113215957-9454fc, revision 1). That card passed R3 decision 2 (advisory block only) at candidate 009f188, then stopped on CI: main was red from syrupy 7.0.0 failing `pytest --collect-only`, a base breakage fixed by #146. A card stopped for CI is not re-admitted, so this card carries the same contract and continues from that branch; PR #145 is superseded by this card's PR.

R13 and acceptance 11 come from the two defects R3 decision 2 found in record writing and summary printing: both ran outside the probe failure handler, so one probe's output could skip the remaining probes and the guard. The third finding of that decision, a probe-raised KeyboardInterrupt, is a non-goal stated above.

Each probe card adds one module, one data directory and one test file. They can run two at a time only if none of them edits a shared registry, so the runner finds probes by listing a directory. The guard and the temporary project root are here because `kb` functions resolve `.data/` paths from `kb.config` at import, and a probe that leaks a write into the owner's corpus must fail the run, not pass it.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_runner.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
