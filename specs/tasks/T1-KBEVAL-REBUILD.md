---
id: T1-KBEVAL-REBUILD
title: "The `rebuild` probe reports the files a second ingest changes, the page differences between three ingest orders, and whether `find_changed_sources` sees a model id change, a template change and a source change"
status: todo
branch: T1-KBEVAL-REBUILD
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-REBUILD
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/rebuild.py
  - bench/knowledge/data/rebuild/sources.jsonl
  - bench/knowledge/data/rebuild/extractions.json
  - bench/knowledge/tests/test_rebuild.py
  - specs/tasks/T1-KBEVAL-REBUILD.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_rebuild.py -q
dod_exit: 0
requirements:
  - R1. `sources.jsonl` shall hold at least 6 rows with `path` (unique, `articles/<name>.md`) and `text`, and `extractions.json` shall map each `path` to an extraction that `kb.ingest.pipeline.ingest_source` accepts for source type `article`, such that at least 3 entity names and at least 3 concept names each occur in the extractions of at least 2 sources.
  - R2. IF a line of `sources.jsonl` is not a JSON object, lacks a field or repeats a `path`, or a `path` has no extraction, or an extraction names no source, THEN the probe shall raise `ValueError` naming the file and the line number or the path.
  - R3. The probe shall write the sources under a raw directory in `ctx.tmp` and ingest each with `ingest_source(path, "article", extraction, wiki_dir=..., raw_dir=...)`, so that no model is called.
  - R4. The arm `idempotence` shall ingest the sources in `path` order into one wiki, take the sha256 of every file under it, ingest them again in the same order, and report `cases` (the source count), `files_after_first`, `files_changed_by_second` (files added, removed or with another hash) and `page_files_changed_by_second` (those of them in a subdirectory of the wiki).
  - R5. The arm `order` shall ingest the sources into three separate wikis in `path` order, in reverse `path` order and in ascending order of the sha256 of `path`, and report, for the pairs `reverse` and `hashed` against `path` order, `page_set_equal_<pair>` (1 or 0, over the files in subdirectories), `pages_differing_bytes_<pair>` and `pages_differing_lines_<pair>` (pages in both whose non-empty lines differ as multisets).
  - R6. The arm `scan` shall, on a wiki and raw directory left by one ingest of all sources, call `kb.compile.compiler.find_changed_sources(raw_dir, manifest_path, save_hashes=False)` and report `listed_clean` (the sources listed with nothing changed), then `sees_model_change` after setting `CLAUDE_SCAN_MODEL`, `CLAUDE_WRITE_MODEL` and `CLAUDE_ORCHESTRATE_MODEL` to other ids, `sees_template_change` after appending a line to `article.yaml` in the temporary project root, and `sees_source_change` after appending a line to one source, each 1 when the call lists at least one source and else 0, with each change undone before the next.
  - R7. IF `listed_clean` is not 0, THEN the `scan` arm shall be `unmeasured` with a reason that holds the count.
  - R8. The probe shall restore the three environment variables to their earlier state and shall write nothing outside `ctx.tmp` and the temporary project root.
  - R9. The probe shall return `invariants` equal to `["I3", "I4"]`.
acceptance:
  - 1. `test_rebuild.py`: the committed files load under R1 and R2 with at least 6 sources, and at least 3 entity names and 3 concept names occur in two or more extractions. [R1] [dod arm 2]
  - 2. Same file, one test per cause of R2: `ValueError` whose message holds the file name and the line number or the path. [R2] [dod arm 2]
  - 3. Same file, `ingest_source` replaced by a stub that writes chosen files: `files_after_first`, `files_changed_by_second` and `page_files_changed_by_second` equal hand-computed values for a second pass that adds one page, rewrites one page and rewrites one root-level file. [R4] [dod arm 2]
  - 4. Same file, the same stub writing order-dependent pages: `page_set_equal_<pair>`, `pages_differing_bytes_<pair>` and `pages_differing_lines_<pair>` equal hand-computed values, and two pages with the same lines in another order count in `bytes` and not in `lines`. [R5] [dod arm 2]
  - 5. Same file, `find_changed_sources` replaced by a stub: the three `sees_` metrics follow the stub's answers, the three variables hold other ids only during the model step and their earlier values after it, and a stub that lists a source on the clean call gives `unmeasured` with the count in the reason. [R6] [R7] [R8] [dod arm 2]
  - 6. Same file, the committed set run through the runner with the real functions and a model function that raises when called: exit 0, `idempotence` and `order` `measured` with `cases` equal to the source count, `scan` `measured` or `unmeasured` with a reason, `invariants` equal to `["I3", "I4"]`. [R3] [R9] [dod arm 2]
depends_on: [T1-KBEVAL-HARNESS-3]
parallelizable_with: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-LINKER, T1-KBEVAL-CITATIONS, T1-KBEVAL-TRACE, T1-KBEVAL-PROVENANCE]
budget: 700
forbid: [any change under src/kb/ templates/ or tests/, a write to the checkout's `templates/` (the template step edits the copy in the temporary project root), a model call or network request, a time or duration in the record, a threshold or pass/fail judgement on a metric]
non_goals: [`compile_wiki` (it calls `ingest_source` with no extraction, so a model would run), the prompt text and the backend as cache inputs (no call is made, so neither can be varied), byte-equal rebuilds on two machines, a run that crosses midnight (the `updated` date of a page may differ between passes; rerun), ingest timing and token cost, any fix]
hygiene: "The extractions stand in for the model, so the arms measure the deterministic part of ingest only: what the code does with equal extractions. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-REBUILD

## Deliverable
The first numbers for lead 6 of `intent/kb-baseline.md` and for invariants I3 and I4: whether ingesting the same source twice is a no-op, whether the order of ingest changes the pages, and which input changes the changed-source scan can see.

## Why
`compile/compiler.py` keys its manifest on the source hash and the template hashes. The lead says the model id is not in the key, so a model change leaves every source marked as compiled. Shared entity and concept pages are built by appending a section per source, so the order of ingest may change them. Both are measurable without a model because `ingest_source` takes a finished extraction.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_rebuild.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
