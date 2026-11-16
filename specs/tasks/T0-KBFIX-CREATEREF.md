---
id: T0-KBFIX-CREATEREF
title: "kb_create_page refuses a source_refs entry holding a character the frontmatter writer deletes (#185)"
status: todo
branch: T0-KBFIX-CREATEREF
worktree: D:\wt\llm-wiki-flywheel\T0-KBFIX-CREATEREF
allow_paths:
  - src/kb/mcp/quality.py
  - tests/test_kbfix_create_page_stripped_ref.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T0-KBFIX-CREATEREF.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_create_page_stripped_ref.py tests/test_mcp_quality_new.py tests/test_backlog_by_file_cycle4.py tests/test_tier1_audit_v095.py tests/test_mcp_core.py -q
dod_exit: 0
requirements:
  - R1. WHEN a `source_refs` entry passed to `kb_create_page` holds a character that `kb.utils.text.yaml_sanitize` removes, `kb_create_page` shall return an `Error:` string and create no page and write no log line.
acceptance:
  - 1. `test_kbfix_create_page_stripped_ref.py`, on every platform: for an existing real file `raw/articles/b<c>.md` with each of DEL U+007F, NEL U+0085, U+2028, U+2029, BOM U+FEFF, RLO U+202E and LRI U+2066, `kb_create_page` with that entry returns a string starting `Error:` that contains `frontmatter cannot keep` and the entry's `repr`, and that `yaml_sanitize` leaves unchanged; every file under the test sandbox keeps its bytes and no file is added. [R1] [dod arm 2]
  - 2. Same file, POSIX only (skipped on Windows, whose file names cannot hold C0 controls): U+0001, VT U+000B and U+001F are refused the same way. [R1] [dod arm 2]
  - 3. Same file, every platform: `source_refs="raw/articles/a.md,raw/articles/b\x85.md"`, where both files exist, is refused the same way, so a valid first entry does not let the page through. [R1] [dod arm 2]
  - 4. Same file, controls: an existing `raw/articles/café.md` (every platform) and `raw/articles/b<TAB>.md` (POSIX only) are accepted (`Created:`), and the page's frontmatter `source:` list, read back with `frontmatter.loads`, holds the entry unchanged. [dod arm 2]
  - 5. Every DoD test file passes and no existing test is edited; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 160
sweep: "Six paths: one src file, one new test file, three doc files, this card. `grep -ln kb_create_page tests/`: `test_mcp_quality_new.py`, `test_backlog_by_file_cycle4.py`, `test_tier1_audit_v095.py`, `test_mcp_core.py` call it and are in the DoD; `test_ingest.py` matches it only in an error message and `test_cycle95_mcp_async_offload.py` only in its tool-name list; both run in the full suite. The check goes in the existing per-entry validation loop (`mcp/quality.py:513`), before the existence check, so no file system call sees a refused entry."
forbid:
  - "a change to `kb.utils.text.yaml_escape` / `yaml_sanitize`, to the title escaping (`safe_title`), or to `ingest_source`"
  - "any edit to an existing test"
  - "a model call or network request in tests"
non_goals:
  - "an entry holding CR or LF: `yaml_escape` writes them as `\\r` / `\\n` and the entry reads back unchanged (shown for the same `- \"{yaml_escape(s)}\"` form in #179), and `kb_create_page` writes no line-oriented file holding the entry, so it is not refused here; on Windows such a file cannot exist and the existing check refuses it as missing"
  - "the title: `yaml_escape(title)` deletes these characters from a title on purpose"
  - "pages already created with a shortened `source:` entry"
diagnosis:
  root_cause: "`kb_create_page` builds each `source:` entry as `yaml_escape(s)`, and `yaml_escape` first runs `yaml_sanitize`, which deletes C0/C1 controls other than TAB, LF and CR, DEL, NEL, U+2028, U+2029, the BOM and bidi marks. The tool checks that the cited raw file exists before writing, so an existing file whose name holds one of these characters passes and the page cites another name. Reproduced on main d38dd31 in the `tmp_kb_env` sandbox: with `raw/articles/b\\x85.md` on disk the call returns `Created` and the frontmatter `source:` reads `raw/articles/b.md`."
  same_class: "`ingest_source` refuses the same set since #184 (T0-KBFIX-STRIPREF) with the same predicate, `yaml_sanitize(s) != s`. No other writer puts a source reference through `yaml_escape` (sweep of `yaml_escape(` in #184's card)."
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixtures as bytes. Every call runs inside `tmp_kb_env`. RED: acceptance 1 and 3 fail on the unfixed code (the call returns `Created:`) on Windows; acceptance 2 and the TAB case of acceptance 4 are skipped on Windows and run in CI (ubuntu-latest); the café case passes on the unfixed code as the control."
---

# T0-KBFIX-CREATEREF

## Deliverable
`kb_create_page` returns `Error: source_ref <repr> holds a character the wiki frontmatter cannot keep ...` when an entry of `source_refs` holds a character `yaml_sanitize` removes, before any file system access for that entry and before the page or log line is written.

## Why
Issue #185, the `kb_create_page` sibling of #183. A page created this way cites a raw file that does not exist.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_create_page_stripped_ref.py tests/test_mcp_quality_new.py tests/test_backlog_by_file_cycle4.py tests/test_tier1_audit_v095.py tests/test_mcp_core.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED at f5994e0: `test_create_page_refuses_an_entry_holding_a_character_the_frontmatter_deletes[del,nel,line-separator,paragraph-separator,bom,rlo,lri]` and `test_create_page_refuses_a_bad_entry_after_a_valid_one` 8 failed (`AssertionError`: the call returned `Created: concepts/probe ...`), `test_create_page_keeps_an_entry_the_frontmatter_can_hold[non-ascii]` passed, 4 POSIX cases skipped (Windows).

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. existing real files with DEL, NEL, U+2028, U+2029, BOM, RLO, LRI: `Error:`, `frontmatter cannot keep`, `repr`, message unchanged by `yaml_sanitize`, sandbox unchanged | `test_create_page_refuses_an_entry_holding_a_character_the_frontmatter_deletes[del,nel,line-separator,paragraph-separator,bom,rlo,lri]` | pass |
| 2. POSIX real files with U+0001, VT, U+001F refused the same way | `test_create_page_refuses_an_entry_holding_a_character_the_frontmatter_deletes[soh,vt,us]` | skipped on Windows; runs in CI (ubuntu-latest) |
| 3. a bad entry after a valid one is refused | `test_create_page_refuses_a_bad_entry_after_a_valid_one` | pass |
| 4. controls `café.md` and (POSIX) `b<TAB>.md`: `Created:`, `source:` equals the entry | `test_create_page_keeps_an_entry_the_frontmatter_can_hold[non-ascii,tab]` | non-ascii pass; tab skipped on Windows, runs in CI |
| 5. DoD green, no existing test edited, CHANGELOG / CHANGELOG-history entries, CLAUDE.md counts | DoD below; `git diff main --stat -- tests/` lists only the new file; `python scripts/verify_docs.py`: 3985 tests, 227 files, docs in sync | pass (reviewer-verified) |

Attempt 2 (repair of R3 decision 1, verdict `.review/T0-KBFIX-CREATEREF.r3.1.5183a1ce.json` on 8c05e88, F1 `validation-after-lossy-trim`). F1 RED at 3d028a8 against 8c05e88's src: `test_create_page_refuses_an_entry_the_strip_would_shorten[nel-only,separator-only-after-valid,trailing-nel,leading-separator]` 4 failed, `test_create_page_still_strips_spaces_around_entries` passed. Repair: the check runs on each comma-separated entry as given, before `strip()` and the empty-entry filter. The only other comma-list splits in `quality.py` (`:199`, `:232`) are page-id lists, never written through `yaml_escape`.

| Input form of the repair hunk | Covering test | Result |
|---|---|---|
| entry holding a deleted character inside it | `test_create_page_refuses_an_entry_holding_a_character_the_frontmatter_deletes[*]` | pass (POSIX cases in CI) |
| entry made only of a deleted character (F1) | `[nel-only]`, `[separator-only-after-valid]` of `test_create_page_refuses_an_entry_the_strip_would_shorten` | pass |
| deleted character at an entry's end or start (F1) | `[trailing-nel]`, `[leading-separator]` | pass |
| bad entry after a valid one | `test_create_page_refuses_a_bad_entry_after_a_valid_one` | pass |
| spaces around entries (still stripped) | `test_create_page_still_strips_spaces_around_entries` | pass |
| entry `yaml_sanitize` keeps (`café`, TAB) | `test_create_page_keeps_an_entry_the_frontmatter_can_hold[non-ascii,tab]` | pass (tab in CI) |
| empty `source_refs`, empty entries (`a,,b`) | unchanged path: `""` passes the check and is dropped by the filter, as before; existing `kb_create_page` tests in the DoD | pass |
