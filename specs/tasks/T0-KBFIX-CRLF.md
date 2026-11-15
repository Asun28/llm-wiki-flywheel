---
id: T0-KBFIX-CRLF
title: "Wikilink injection writes a page back with its own line endings: CRLF, LF and lone CR are kept (#168)"
status: todo
branch: T0-KBFIX-CRLF
worktree: D:\wt\llm-wiki-flywheel\T0-KBFIX-CRLF
allow_paths:
  - src/kb/compile/linker.py
  - tests/test_kbfix_linker_crlf.py
  - tests/test_cycle18_linker_lock.py
  - tests/test_cycle19_inject_wikilinks_batch.py
  - docs/reference/architecture.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T0-KBFIX-CRLF.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_linker_crlf.py tests/test_cycle18_linker_lock.py tests/test_cycle19_inject_wikilinks_batch.py tests/test_cycle19_inject_batch_e2e.py tests/test_kbfix_linker_headings.py tests/test_kbfix_code_mask_redos.py tests/test_compile.py tests/test_ingest.py -q
dod_exit: 0
requirements:
  - R1. WHEN `inject_wikilinks` or `inject_wikilinks_batch` writes a page, the written file shall equal the file as read before the call apart from the inserted wikilink, so every CRLF, LF and lone CR line ending is kept.
  - R2. WHEN a page saved with CRLF line endings holds the title only inside an ATX heading line, `inject_wikilinks` and `inject_wikilinks_batch` shall leave the page unwritten.
  - R3. The four existing linker spy tests named in acceptance 4 shall observe the linker's page reads through `Path.read_bytes` instead of `Path.read_text`, with their assertions unchanged.
acceptance:
  - 1. `test_kbfix_linker_crlf.py`: a page saved with CRLF everywhere (frontmatter, `## Hydration`, a blank line, `Hydration matters.`) and the same page saved with LF, each injected through `inject_wikilinks`, `inject_wikilinks_batch` (disk walk) and `inject_wikilinks_batch(pages=load_all_pages(wiki))`, return `["entities/bread"]`, and the file's bytes equal the original bytes with `Hydration matters.` replaced by `[[concepts/hydration|Hydration]] matters.`. [R1] [dod arm 2]
  - 2. Same file, same three call paths: a page whose lines end in a mix of LF, CRLF and one lone CR keeps every line ending byte-identical apart from the inserted link. [R1] [dod arm 2]
  - 3. Same file, same three call paths: a CRLF page whose only title match is the heading `## Hydration` returns `[]`, and its bytes and mtime are unchanged. [R2] [dod arm 2]
  - 4. In `test_cycle18_linker_lock.py` (`test_inject_wikilinks_sequence_order`, `test_inject_wikilinks_toctou_skip`) and `test_cycle19_inject_wikilinks_batch.py` (`test_read_budget_bounded`, `test_revert_to_per_target_inject_would_inflate_read_count`) the spy patches `Path.read_bytes` instead of `Path.read_text` (the race spy returns its content encoded as UTF-8); every assertion, event name order and threshold is unchanged, and all four pass. No other existing test is edited (reviewer-verified against the diff). [R3] [dod arm 2]
  - 5. The `Wikilink injection` bullet of `docs/reference/architecture.md` states that both injectors read pages with newline translation off, so a page keeps its line endings; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 220
sweep: "Nine paths: one src file, one new and two existing test files, four doc files, this card. `Path.read_text` in linker.py: :136 (`resolve_wikilinks`) and :195 (`build_backlinks`) read only and never write; :265 and :287 (`inject_wikilinks` peek and locked read) and :455 and :540 (`inject_wikilinks_batch` disk-walk peek and `_process_inject_chunk` locked read) feed `atomic_text_write`; all four switch to one reader. `grep -rn 'read_text' tests/` for spies: four tests patch `Path.read_text` on the linker path (acceptance 4); the other `Path.read_text` patches (feedback store, verdicts, compile manifest, inline callouts, ingest index writers, source read budget, refiner) never reach the linker. CI runs Python 3.12, where `Path.read_text` has no `newline` argument."
forbid:
  - "a change to `resolve_wikilinks`, `build_backlinks`, `_mask_code_blocks`, `_mask_for_injection`, `_CODE_MASK_RE` or `_ATX_HEADING_RE`"
  - "a change to `kb.utils.io.atomic_text_write` or any other page writer outside linker.py"
  - "any edit to an existing test other than the four spies of acceptance 4"
  - "a model call or network request in tests"
non_goals:
  - "the same read pattern in other page writers: `ingest/pipeline.py:857` (`_update_existing_page_body`), `ingest/evidence.py:200` (`append_evidence_trail`) and `lint/checks/dead_links.py:80` (`fix_dead_links`) still turn CRLF into LF (follow-up issue); `review/refiner.py:144` converts CRLF to LF on purpose"
  - "the `pages=` bundle content a caller passes to `inject_wikilinks_batch`: it is used only for the pre-lock peek, and the written content always comes from the locked read"
  - "converting existing pages between line-ending styles"
diagnosis:
  root_cause: "The linker reads pages with `Path.read_text(encoding='utf-8')`, which applies universal-newline translation (CRLF and lone CR become LF), then writes the modified text with `atomic_text_write`, whose `newline='\\n'` writes the text unchanged. The read, not the writer, drops the CRs. Reproduced on main 1f8df97: a CRLF page goes through both injectors and comes back with 0 of its 13 CRs."
  same_class: "Three other read-modify-write page writers use the same read (non_goals, follow-up issue). The heading mask still recognises a CRLF heading: `[^\\n]*` keeps the trailing CR inside the heading span, and `FRONTMATTER_RE` accepts `\\r?\\n`."
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixtures as BYTES (`write_bytes`), since `write_text` on Windows turns `\\n` into CRLF. RED: acceptance 1-3 fail on the unfixed code with an AssertionError on the page bytes (CRLF and mixed cases; the LF case passes as a control). Acceptance 4's moved spies fail on the unfixed code except `test_read_budget_bounded`, whose bound a read count of 0 also meets; its revert partner shows the count is live. Run the full suite locally before SHIP."
doc_sync: docs/reference/architecture.md
---

# T0-KBFIX-CRLF

## Deliverable
`inject_wikilinks` and `inject_wikilinks_batch` read every page they may rewrite through one helper that decodes the file's bytes as UTF-8 with no newline translation, so a written page keeps its line endings byte for byte apart from the inserted link.

## Why
Issue #168. Owner ruling 2026-11-15 deferred this from T1-KBFIX-FROMHEAD (R3 findings F2/F3). A page saved with CRLF is rewritten to LF on every link insertion, which shows up as a whole-file diff in an editor or in git.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_linker_crlf.py tests/test_cycle18_linker_lock.py tests/test_cycle19_inject_wikilinks_batch.py tests/test_cycle19_inject_batch_e2e.py tests/test_kbfix_linker_headings.py tests/test_kbfix_code_mask_redos.py tests/test_compile.py tests/test_ingest.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
