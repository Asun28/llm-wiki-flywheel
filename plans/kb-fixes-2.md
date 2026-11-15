---
slug: kb-fixes-2
title: "Fix the four open issues #175, #163, #157 and #148"
spec: specs/kb-fixes-2.md
size: T1
status: accepted
created: 2026-11-15T19:15:00Z
---

# Plan: Fix the four open issues #175, #163, #157 and #148 (from specs/kb-fixes-2.md)

## 1. Goal and boundaries
Fix #175 in `src/kb/` and #163, #157, #148 in `bench/knowledge/`, each with reproducing tests, under the owner decisions in `intent/kb-fixes-2.md`. Cut: `refine_page`, the `_sources.md` / `index.md` / contradictions writers, `save_page_frontmatter`, rerunning the committed Phase 0 baseline. Success: spec acceptance 1-6 on the final integrated SHA.

## 2. Minimal acceptable loop
#175 splits in two: the shared helper with the linker moved onto it (the 27 linker CRLF tests prove the move changes no linker output), then the three writers. Each bench issue is one card. Each card: RED test, fix, GREEN, R3, merge. Then VERIFY-ARC.

## 3. Tech stack
none this version (stdlib `difflib` only)

## 4. Directory structure
none this version (one new module `src/kb/utils/line_ends.py`; new test files only)

## 4.5 Module design
- `kb.utils.line_ends` (LINEENDS): `read_page_text`, `restore_line_ends` (line diff; most-used end for added lines). Leaf module.
- `kb.compile.linker` (LINEENDS): drops `_read_page` / `_restore_line_ends`, imports the helper.
- `kb.ingest.pipeline`, `kb.ingest.evidence`, `kb.lint.checks.dead_links` (CRLFWRITERS): read through the helper, write its restore.
- `bench/knowledge/tests/test_baseline.py` (ALTFIG): `plain()` renders image alt children.
- `bench/knowledge/probes/trace.py` (HTMLBLOCK): `html` leaf kind in `classify_lines`.
- `bench/knowledge/run.py` (RUNNERERR): scandir probe listing, `--out` usage checks, read-only record removal, exit code before diagnostics, broken-stdout shutdown.

## 5. Data model and state machine
none this version

## 6. Contracts and core interfaces
`kb.utils.line_ends.read_page_text(path) -> tuple[str, list[str]]` and `restore_line_ends(text, original, ends) -> str` (new). `run.py` exit codes keep their meaning. No frozen contract changes. See spec "Interfaces and contracts".

## Files that change
- src/kb/utils/line_ends.py (new)
- src/kb/compile/linker.py
- src/kb/ingest/pipeline.py
- src/kb/ingest/evidence.py
- src/kb/lint/checks/dead_links.py
- tests/test_kbfix_line_ends.py (new)
- tests/test_kbfix_crlf_writers.py (new)
- tests/test_ingest.py (one read-count spy retargeted from `read_text` to `read_bytes`)
- bench/knowledge/tests/test_baseline.py
- bench/knowledge/probes/trace.py
- bench/knowledge/tests/test_trace.py
- bench/knowledge/run.py
- bench/knowledge/tests/test_runner.py
- bench/knowledge/README.md (runner exit codes and `--out` rules)
- docs/knowledge-baseline.md (two dated notes)
- CHANGELOG.md
- CHANGELOG-history.md
- CLAUDE.md (test counts)
- docs/reference/architecture.md
- docs/reference/module-map.md

## Order of work
1. T1-KBFIX-LINEENDS (freeze): helper unit tests RED, then `kb.utils.line_ends` and the linker switch; the 27 linker CRLF tests unchanged.
2. T1-KBFIX-CRLFWRITERS (after LINEENDS merges): CRLF regression per writer RED, then the three writers.
3. T1-KBEVAL-ALTFIG: two alt-text regressions RED, then `plain()`.
4. T1-KBEVAL-HTMLBLOCK: example 161 and per-type regressions RED, then the `html` leaf; the two report notes.
5. T1-KBEVAL-RUNNERERR: one regression per R15-R21 RED, then `run.py`.
6. VERIFY-ARC on the final SHA.

## 7. Task split (dependencies and parallel windows)

| Card | Priority | Output | depends_on | Parallel window | Freeze point |
|---|---|---|---|---|---|
| T1-KBFIX-LINEENDS | MUST | shared line-end helper; linker on it, output unchanged | - | - | yes |
| T1-KBFIX-CRLFWRITERS | MUST | re-ingest, evidence append and lint --fix keep CRLF | T1-KBFIX-LINEENDS | - | - |
| T1-KBEVAL-ALTFIG | MUST | baseline test counts formatted alt-text figures | - | - | - |
| T1-KBEVAL-HTMLBLOCK | MUST | trace probe keeps prose after an HTML block | - | - | - |
| T1-KBEVAL-RUNNERERR | MUST | runner reports the six error paths, no input-dir writes | - | - | - |

One R3 reviewer slot and shared `CHANGELOG.md` / `CHANGELOG-history.md`, so cards run one at a time (no parallel window).

## Risks
- The new restore must give the linker the same bytes as the one-splice restore. The 27 tests of `tests/test_kbfix_linker_crlf.py` are the proof and stay unchanged; LINEENDS also runs every linker test file.
- `difflib.SequenceMatcher` with `autojunk=False` is quadratic in the worst case. Pages are bounded by ingest limits; LINEENDS adds a timing check on a 5,000-line page.
- Existing tests spy on `Path.read_text`: `tests/test_ingest.py:1457` counts reads in `_update_existing_page` and reads 0 after the switch to `read_bytes`. CRLFWRITERS retargets that one spy (as #174 did for 4 linker tests); no assertion changes. `tests/test_cycle35_ingest_index_writers.py` spies on the `_sources.md` / `index.md` writers, which do not change.
- The baseline report's number scan (`test_every_number_in_the_report_comes_from_summary_or_labels`) flags any bare digit: the HTMLBLOCK notes put the date and card id in backticks.
- Closed-pipe and read-only-file tests differ by platform: RUNNERERR uses a real subprocess for the pipe and `os.chmod` for read-only; a symlink test skips where the OS refuses symlink creation (Windows without privilege), and CI on ubuntu runs it.
- SHRINK-2 lesson: CRLFWRITERS changes shared writers, so the full suite runs locally before SHIP.

## Proof
- Per card: its `dod_command` (ruff + the card's tests + the existing test files of the touched module), RED receipt before the fix.
- Arc: `python -m pytest -q`, `python -m pytest bench/knowledge/tests -q`, `python bench/knowledge/run.py --out <scratch>` (exit 0, trace numbers recorded against Phase 0), and a scratch CRLF round trip: a CRLF copy of a demo page through re-ingest, an evidence append and `kb lint --fix`, every line end still CRLF.

## 10. After merge
none this version (development-only target). Each closed issue gets a comment naming its PR and evidence.
