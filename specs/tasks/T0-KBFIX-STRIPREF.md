---
id: T0-KBFIX-STRIPREF
title: "Ingest refuses a source path holding a character the frontmatter writer deletes (#183)"
status: todo
branch: T0-KBFIX-STRIPREF
worktree: D:\wt\llm-wiki-flywheel\T0-KBFIX-STRIPREF
allow_paths:
  - src/kb/ingest/pipeline.py
  - tests/test_kbfix_source_ref_stripped_chars.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T0-KBFIX-STRIPREF.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_source_ref_stripped_chars.py tests/test_kbfix_source_ref_line_break.py tests/test_kbfix_crlf_writers.py tests/test_kbfix_ingest_template_baseline.py tests/test_ingest.py -q
dod_exit: 0
requirements:
  - R1. WHEN the source reference that `ingest_source` builds holds a character that `kb.utils.text.yaml_sanitize` removes, `ingest_source` shall raise `ValueError` before it writes any file.
acceptance:
  - 1. `test_kbfix_source_ref_stripped_chars.py`, on every platform: real files `raw/articles/b<c>.md` for each of DEL U+007F, NEL U+0085, U+2028, U+2029, BOM U+FEFF, RLO U+202E and LRI U+2066, ingested with no patch, raise `ValueError` matching `frontmatter cannot keep`, whose message holds the reference as its `repr` and that `yaml_sanitize` leaves unchanged; every file under the test sandbox keeps its bytes and no file is added. [R1] [dod arm 2]
  - 2. Same file, POSIX only (skipped on Windows, whose file names cannot hold C0 controls): real files holding U+0001, VT U+000B and U+001F are refused the same way. [R1] [dod arm 2]
  - 3. Same file, controls: after `raw/articles/a.md` creates the entity page `entities/bread.md`, a real file `raw/articles/café.md` (every platform) and `raw/articles/b<TAB>.md` (POSIX only) naming the same entity ingest, and the entity page's frontmatter `source:` list, read back with `frontmatter.loads`, holds the reference unchanged. [dod arm 2]
  - 4. Every DoD test file passes and no existing test is edited; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 160
sweep: "Six paths: one src file, one new test file, three doc files, this card. `grep -n 'yaml_escape(\\|yaml_sanitize(' src/kb`: in ingest only `pipeline.py:883` (`_update_existing_page_body`, the update path) writes a source reference through `yaml_escape`; the new-page writer `_write_wiki_page` uses `frontmatter.dumps`, which escapes these characters and keeps the reference. Outside ingest, `mcp/quality.py:547` (`kb_create_page`) writes its source entries through `yaml_escape` (non_goals). The other hits escape titles, URLs, statuses and source types, not source references."
forbid:
  - "a change to `kb.utils.text.yaml_escape` / `yaml_sanitize`, `kb.utils.paths.make_source_ref`, `_update_existing_page_body`, `_write_wiki_page` or `lint/checks/consistency.py`"
  - "any edit to an existing test"
  - "a model call or network request in tests"
non_goals:
  - "`kb_create_page` (`mcp/quality.py:547`): a `source_refs` entry naming an existing raw file that holds such a character is still written without it (follow-up issue)"
  - "escaping these characters in the update writer instead of refusing them: `yaml_sanitize` deletes bidi marks on purpose (audit-log confusion), and the owner ruled refusal at ingest for the CR/LF sibling (#179)"
  - "renaming or migrating raw files already on disk, and existing pages whose `source:` entry already lost a character"
diagnosis:
  root_cause: "`_update_existing_page_body` writes the new `source:` entry as `yaml_escape(source_ref)`, and `yaml_escape` first runs `yaml_sanitize`, which deletes C0/C1 controls other than TAB, LF and CR, DEL, NEL, U+2028, U+2029, the BOM and bidi marks. Reproduced on main 75c08b4 with real files on Windows (NEL, U+2028, U+202E, BOM, DEL): the first ingest's summary page keeps `raw/articles/b<c>.md` (`frontmatter.dumps` escapes it), and the entity page the second source updates records `raw/articles/b.md`, which names another file. #183 also said the new-page writer loses it; that part does not reproduce. The line separators among these (NEL, U+2028, U+2029, VT, FF, U+001C-U+001E) also end a line for `str.splitlines`, which `_update_sources_mapping` uses to merge a re-ingest."
  same_class: "Refused in `ingest_source` right after the #179 CR/LF check, which runs first, so `yaml_sanitize` never sees CR. The predicate is `yaml_sanitize(source_ref) != source_ref`, so the refusal follows the deleted set if that set changes. `kb_create_page` is the one other writer of a source reference through `yaml_escape` (non_goals)."
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixtures as bytes. Every ingest runs inside `tmp_kb_env`; never ingest outside the sandbox. RED: acceptance 1 fails on the unfixed code (DID NOT RAISE) on Windows; acceptance 2 and the TAB case of acceptance 3 are skipped on Windows and run in CI (ubuntu-latest); the café case passes on the unfixed code as the control."
---

# T0-KBFIX-STRIPREF

## Deliverable
`ingest_source` raises `ValueError` when the reference built from the source path holds a character `yaml_sanitize` removes, before any write. The message shows the reference through `repr`.

## Why
Issue #183. A re-ingest that adds such a source to an existing page records a `source:` entry without the character, so the page cites a file that does not exist. The owner ruled refusal at ingest for the CR/LF case (#179); this card applies it to the rest of the set the frontmatter writer deletes.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_source_ref_stripped_chars.py tests/test_kbfix_source_ref_line_break.py tests/test_kbfix_crlf_writers.py tests/test_kbfix_ingest_template_baseline.py tests/test_ingest.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED at 0e3dde0: `test_ingest_refuses_a_reference_holding_a_character_the_frontmatter_deletes[del,nel,line-separator,paragraph-separator,bom,rlo,lri]` 7 failed (`DID NOT RAISE <class 'ValueError'>`), `test_an_updated_page_keeps_a_reference_the_frontmatter_can_hold[non-ascii]` passed, 4 POSIX cases skipped (Windows).

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. real files with DEL, NEL, U+2028, U+2029, BOM, RLO, LRI refused: `ValueError` matching `frontmatter cannot keep`, `repr` in the message, message unchanged by `yaml_sanitize`, sandbox snapshot unchanged | `test_ingest_refuses_a_reference_holding_a_character_the_frontmatter_deletes[del,nel,line-separator,paragraph-separator,bom,rlo,lri]` | pass |
| 2. POSIX real files with U+0001, VT, U+001F refused the same way | `test_ingest_refuses_a_reference_holding_a_character_the_frontmatter_deletes[soh,vt,us]` | skipped on Windows; runs in CI (ubuntu-latest) |
| 3. controls: `café.md` and (POSIX) `b<TAB>.md` ingest; the updated entity page's `source:` list holds the reference unchanged | `test_an_updated_page_keeps_a_reference_the_frontmatter_can_hold[non-ascii,tab]` | non-ascii pass; tab skipped on Windows, runs in CI |
| 4. DoD green, no existing test edited, CHANGELOG / CHANGELOG-history entries, CLAUDE.md counts | DoD below; `git diff main --stat -- tests/` lists only the new file; `python scripts/verify_docs.py`: 3967 tests, 226 files, docs in sync | pass (reviewer-verified) |
