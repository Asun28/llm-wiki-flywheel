---
id: T1-KBFIX-TPLBASE
title: "`ingest_source` records the `_template/<type>` baseline when the manifest has none, so `find_changed_sources` lists nothing on a clean ingest-only wiki (#160)"
status: todo
branch: T1-KBFIX-TPLBASE
worktree: D:\wt\llm-wiki-flywheel\T1-KBFIX-TPLBASE
plan_ref: plans/kb-defects-1.md#order-of-work
allow_paths:
  - src/kb/ingest/pipeline.py
  - tests/test_kbfix_ingest_template_baseline.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T1-KBFIX-TPLBASE.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_ingest_template_baseline.py tests/test_ingest.py tests/test_cycle83_ingest_crash_atomicity.py tests/test_cycle17_compile_manifest.py tests/test_cycle19_manifest_key_consistency.py tests/test_compile.py -q
dod_exit: 0
requirements:
  - R1. WHEN `ingest_source` commits a source hash and the manifest has no `_template/<source_type>` key and `kb.compile.compiler._template_hashes()` reports one for that type, `ingest_source` shall write that key with the reported hash in the same `file_lock(HASH_MANIFEST)` span and the same manifest save as the source hash.
  - R2. `ingest_source` shall not change an existing `_template/<source_type>` value and shall not write a `_template/` key for any other type.
  - R3. WHEN a wiki is built only by `ingest_source` and nothing has changed since, `find_changed_sources(raw_dir, manifest_path, save_hashes=False)` shall return two empty lists.
  - R4. WHEN the manifest held a `_template/<source_type>` value different from the current template hash before an ingest of that type, `find_changed_sources(..., save_hashes=False)` after the ingest shall still list the sources of that type as changed.
acceptance:
  - 1. `test_kbfix_ingest_template_baseline.py`: three `article` sources ingested with a supplied extraction (no model call) into a `tmp_kb_env` wiki; then `find_changed_sources(raw_dir, manifest, save_hashes=False)` returns `([], [])`, and the manifest holds `_template/article` equal to `_template_hashes()["_template/article"]` and no other `_template/` key. [R1] [R2] [R3] [dod arm 2]
  - 2. Same file: with `_template/article` preset to a value unequal to the current hash, a further ingest leaves that value byte-equal, and the scan lists every article source as changed. [R2] [R4] [dod arm 2]
  - 3. Same file: a spy on the manifest save shows the source hash and the `_template/article` key land in one save inside one `file_lock(HASH_MANIFEST)` acquisition. [R1] [dod arm 2]
  - 4. Same file: when `_template_hashes()` reports no key for the type (template file absent), ingest writes the source hash and no `_template/` key. [R1] [dod arm 2]
  - 5. The existing ingest, crash-atomicity, manifest and compile tests in the DoD pass with no edit to them. [dod arm 2]
  - 6. `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the test and test-file counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 200
sweep: "Six paths: one src file, one new test file, three doc files, this card. The manifest commit has one call site (`pipeline.py:1613`, `_commit_ingest_manifest`); both duplicate checks (`pipeline.py:331`, `:400`) already skip `_template/` keys, so a template hash is never read as a source hash."
forbid: [any change to `find_changed_sources` or `compile_wiki`, overwriting an existing `_template/` value, a second manifest lock acquisition per ingest, a model call or network request in tests]
non_goals: [backfilling `_template/` keys on existing wikis outside an ingest (the next ingest of the type or the next `compile_wiki` writes them), treating a missing key as "no baseline" in the scan (owner chose the ingest-side fix), the model id as a cache input (lead 6, separate)]
diagnosis:
  root_cause: "Only `compile_wiki` writes `_template/<type>`; `ingest_source` records `manifest[source_ref]` alone (`_commit_ingest_manifest`, pipeline.py:428). `find_changed_sources` reads a missing template key as a template change (compiler.py:270), so an ingest-only wiki has no baseline and every source of every type with files is listed."
  same_class: "Other manifest writers: `compile_wiki` (writes the keys), `find_changed_sources(save_hashes=True)` (writes the keys), `_clear_ingest_manifest_entry` (removes a source key only). None needs the change."
hygiene: "Run the DoD with the main checkout's `.venv` active. RED: acceptance 1 fails on the unfixed code because the scan lists the three sources, not with an import or collection error."
doc_sync: CHANGELOG.md
---

# T1-KBFIX-TPLBASE

## Deliverable
A wiki built by `ingest_source` alone carries the template baseline for each ingested source type, so the changed-source scan reports nothing when nothing changed. A baseline written by `compile_wiki` is never overwritten by ingest.

## Why
Issue #160. The first incremental `kb compile` after ingest-only builds treated every source as changed, and the knowledge bench `rebuild.scan` arm could not be measured (`listed_clean=6`).

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_ingest_template_baseline.py tests/test_ingest.py tests/test_cycle83_ingest_crash_atomicity.py tests/test_cycle17_compile_manifest.py tests/test_cycle19_manifest_key_consistency.py tests/test_compile.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
