---
id: T0-KBFIX-CRLF
title: "Wikilink injection writes a page back with its own CRLF or LF line endings (#168)"
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
  - R1. WHEN `inject_wikilinks` or `inject_wikilinks_batch` writes a page, the written file shall equal the file as read before the call apart from the inserted wikilink, keeping every CRLF and LF line ending; a lone CR is written as LF, as before this card.
  - R2. WHEN a page saved with CRLF line endings holds the title only inside an ATX heading line, `inject_wikilinks` and `inject_wikilinks_batch` shall leave the page unwritten.
  - R3. The four existing linker spy tests named in acceptance 4 shall observe the linker's page reads through `Path.read_bytes` instead of `Path.read_text`, with their assertions unchanged.
acceptance:
  - 1. `test_kbfix_linker_crlf.py`: a page saved with CRLF everywhere (frontmatter, `## Hydration`, a blank line, `Hydration matters.`) and the same page saved with LF, each injected through `inject_wikilinks`, `inject_wikilinks_batch` (disk walk) and `inject_wikilinks_batch(pages=load_all_pages(wiki))`, return `["entities/bread"]`, and the file's bytes equal the original bytes with `Hydration matters.` replaced by `[[concepts/hydration|Hydration]] matters.`. The same holds, through the same three call paths, for a CRLF page with no final line end; for a title holding a line break matched across a CRLF line end (that one end goes with the replaced text, every other stays CRLF); and for a CRLF page whose frontmatter fits `FRONTMATTER_RE`'s 10,000-character bound only with LF ends (the frontmatter stays unlinked; R3 F2). [R1] [dod arm 2]
  - 2. Same file, same three call paths: a page whose lines end in a mix of LF and CRLF keeps every line ending byte-identical apart from the inserted link; a page whose lines all end in a lone CR is written with LF endings, its `## Hydration` heading unlinked and `Hydration matters.` linked (as before this card). [R1] [dod arm 2]
  - 3. Same file, same three call paths: a CRLF page whose only title match is the heading `## Hydration`, and a CRLF page whose only match for the title `###` is the empty heading `###` (R3 F1), each return `[]`, and their bytes and mtime are unchanged. [R2] [dod arm 2]
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
  - "keeping lone CR line endings: `FRONTMATTER_RE` and `_ATX_HEADING_RE` recognise only LF and CRLF line ends, so the reader turns a lone CR into LF before masking, as `Path.read_text` did; kept, it would hide the frontmatter and headings of a lone-CR page from the masks"
diagnosis:
  root_cause: "The linker reads pages with `Path.read_text(encoding='utf-8')`, which applies universal-newline translation (CRLF and lone CR become LF), then writes the modified text with `atomic_text_write`, whose `newline='\\n'` writes the text unchanged. The read, not the writer, drops the CRs. Reproduced on main 1f8df97: a CRLF page goes through both injectors and comes back with 0 of its 13 CRs."
  same_class: "Three other read-modify-write page writers use the same read (non_goals, follow-up issue). The masks and `FRONTMATTER_RE` were written for LF text (an empty ATX heading needs `$` right after its hashes; the frontmatter bound counts characters, CRs included), so they keep running on the LF text and only the write restores each line's CRLF (R3 decision 1, F1/F2)."
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixtures as BYTES (`write_bytes`), since `write_text` on Windows turns `\\n` into CRLF. RED: the CRLF cases of acceptance 1 and the LF/CRLF case of acceptance 2 fail on the unfixed code with an AssertionError on the page bytes; the LF cases of acceptance 1, the lone-CR case of acceptance 2 and all of acceptance 3 pass on it as controls (the unfixed code also masks the heading, after turning its line ends into LF). Acceptance 4's moved spies fail on the unfixed code except `test_read_budget_bounded`, whose bound a read count of 0 also meets; its revert partner shows the count is live. Run the full suite locally before SHIP."
doc_sync: docs/reference/architecture.md
---

# T0-KBFIX-CRLF

## Deliverable
`inject_wikilinks` and `inject_wikilinks_batch` read every page they may rewrite through one helper that returns the page with every line end turned into LF, exactly as `Path.read_text` did, plus the page's own line ends in order. The frontmatter, heading and code masks run on the LF text as before, and the write gives each line its own CRLF or LF end back, so a written page keeps its line ends byte for byte apart from the inserted link.

## Why
Issue #168. Owner ruling 2026-11-15 deferred this from T1-KBFIX-FROMHEAD (R3 findings F2/F3). A page saved with CRLF is rewritten to LF on every link insertion, which shows up as a whole-file diff in an editor or in git.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_linker_crlf.py tests/test_cycle18_linker_lock.py tests/test_cycle19_inject_wikilinks_batch.py tests/test_cycle19_inject_batch_e2e.py tests/test_kbfix_linker_headings.py tests/test_kbfix_code_mask_redos.py tests/test_compile.py tests/test_ingest.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 2 (repair of R3 decision 1, verdict `.review/T0-KBFIX-CRLF.r3.1.4062d0f0.json` on 71ebdf0). RED for F1/F2 at 4a9b908: 5 failed on 71ebdf0 (`[single-empty-heading]`, `[batch-empty-heading]`, near-bound frontmatter through all three paths), all AssertionError. Repair at 091e4eb: `_read_page` returns the LF text `Path.read_text` gave plus the page's line ends; `_restore_line_ends` restores them around the one splice at both write sites.

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. CRLF and LF pages byte-identical apart from the link; CRLF page with no final line end; title spanning a CRLF line end; near-bound CRLF frontmatter (F2), three call paths | `test_page_keeps_its_line_endings[*-crlf,*-lf]`, `test_crlf_page_without_a_final_line_end_keeps_its_ends[*]`, `test_title_spanning_a_crlf_line_end_keeps_the_other_ends[*]`, `test_crlf_frontmatter_near_the_bound_stays_unlinked[*]` | pass |
| 2. LF/CRLF mix kept; lone-CR page written as LF, heading unlinked, body linked | `test_mixed_crlf_and_lf_endings_are_kept[*]`, `test_lone_cr_endings_are_written_as_lf[*]` | pass |
| 3. CRLF page matching only in `## Hydration`, or only in the empty heading `###` for title `###` (F1): `[]`, bytes and mtime unchanged | `test_crlf_page_matching_only_in_a_heading_is_not_written[*-heading,*-empty-heading]` | pass |
| 4. four spies moved to `Path.read_bytes`, assertions unchanged | `test_inject_wikilinks_sequence_order`, `test_inject_wikilinks_toctou_skip`, `test_read_budget_bounded`, `test_revert_to_per_target_inject_would_inflate_read_count`; `git diff main -- tests/test_cycle18_linker_lock.py tests/test_cycle19_inject_wikilinks_batch.py` changes only the patched attribute, the real-function and spy names, the race spy's bytes literal and docstrings | pass |
| 5. architecture bullet, one CHANGELOG / CHANGELOG-history entry each, CLAUDE.md State counts | `python scripts/verify_docs.py`: docs in sync, 3888 tests, 222 files | pass (reviewer-verified) |

| Input form or path of the repair hunks | Covering test | Result |
|---|---|---|
| LF page (no CRLF: `_restore_line_ends` returns the text unchanged) | `test_page_keeps_its_line_endings[*-lf]` | pass |
| CRLF page, final line end present / absent | `test_page_keeps_its_line_endings[*-crlf]`, `test_crlf_page_without_a_final_line_end_keeps_its_ends[*]` | pass |
| mixed LF and CRLF | `test_mixed_crlf_and_lf_endings_are_kept[*]` | pass |
| lone CR (read as LF, written as LF) | `test_lone_cr_endings_are_written_as_lf[*]` | pass |
| splice that removes a line end (title holding a line break) | `test_title_spanning_a_crlf_line_end_keeps_the_other_ends[*]` | pass |
| empty CRLF heading (F1) / CRLF frontmatter near the bound (F2) | `test_crlf_page_matching_only_in_a_heading_is_not_written[*-empty-heading]`, `test_crlf_frontmatter_near_the_bound_stays_unlinked[*]` | pass |
| race: locked read differs from the peek | `test_inject_wikilinks_toctou_skip` | pass |
| `OSError` / `UnicodeDecodeError` from the read | unchanged: both callers keep `except (OSError, UnicodeDecodeError): continue` around `_read_page` | unchanged |

Mutants (not committed; file restored after each): unfixed linker 1f8df97: 18 of 43 fail; attempt-1 linker 71ebdf0: 8 fail; no restore at the single write: 5 fail; no restore at the batch write: 10 fail; restore by line index only (no splice alignment): 3 fail; `inject_wikilinks` peek reverted to `read_text`: 3 fail; batch disk-walk peek reverted to `read_text`: 0 fail (that read only decides whether to lock; the write uses the locked read). Property check (not committed): 20,000 random pages over `a b # space LF CRLF CR` with a random splice; `_restore_line_ends` equals splicing the raw page every time.
