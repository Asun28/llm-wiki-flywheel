---
id: T1-KBFIX-TPLBASE
title: "`ingest_source` records the `_template/<type>` baseline when the manifest has none, so `find_changed_sources` lists nothing on a clean ingest-only wiki (#160)"
status: merged
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

## Attempt evidence

Attempt 1. RED commit `37b5423`, GREEN commit `4430b05`. Tests: `tests/test_kbfix_ingest_template_baseline.py` (5 tests, supplied extractions, `_skip_vector_rebuild=True`, no model call or network).

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. three article ingests, scan returns `([], [])`, manifest holds `_template/article` equal to `_template_hashes()` and no other `_template/` key | `test_ingest_only_wiki_scan_lists_nothing` | pass |
| 2. preset unequal `_template/article` stays byte-equal after an ingest; scan lists every article source | `test_existing_unequal_template_value_is_kept_and_scan_flags_type` | pass |
| 3. source hash and `_template/article` land in one save inside one `file_lock(HASH_MANIFEST)` acquisition | `test_source_hash_and_template_key_land_in_one_locked_save` | pass |
| 4. template file absent: source hash written, no `_template/` key | `test_absent_template_file_writes_no_template_key` | pass |
| 5. existing ingest, crash-atomicity, manifest and compile tests pass unedited | DoD arm 2: `test_ingest.py`, `test_cycle83_ingest_crash_atomicity.py`, `test_cycle17_compile_manifest.py`, `test_cycle19_manifest_key_consistency.py`, `test_compile.py` (`git diff main -- tests/` touches only the new file); 265 passed, 1 skipped | pass |
| 6. one entry under this card id in `CHANGELOG.md` `[Unreleased]` and `CHANGELOG-history.md`; `CLAUDE.md` State counts equal `scripts/verify_docs.py` | `python scripts/verify_docs.py`: collected tests 3798 (attempt 1; 3799 after attempt 2), test file count 217, "docs in sync"; State line reads `3798 tests across 217 test files` (attempt 1) | pass (reviewer-verified) |

RED against the unfixed code (`main` at `aaa4bce`): 3 failed, 2 passed. Failures are all `AssertionError`: the scan listed the three ingested sources (acceptance 1); no save carried `_template/article` (acceptance 3); the manifest had no `_template/article` after the mid-ingest edit (`None == <pre-edit hash>`, lead design test). No import or collection error. The 2 passes are acceptance 2 and 4, which guard behaviour the unfixed code already met (it never wrote a template key). GREEN: DoD exit 0, 265 passed, 1 skipped.

| Input form / failure path | Covering test | Result |
|---|---|---|
| `_template/article` key absent: written with the hash captured at ingest start | `test_ingest_only_wiki_scan_lists_nothing`, `test_source_hash_and_template_key_land_in_one_locked_save` | pass |
| key present, equal to the current hash: left as is (`setdefault`), scan lists nothing | `test_ingest_only_wiki_scan_lists_nothing` (ingests 2 and 3 run with the key present and equal) | pass |
| key present, unequal: left byte-equal, scan lists the type's sources | `test_existing_unequal_template_value_is_kept_and_scan_flags_type` | pass |
| template file absent: no `_template/` key written | `test_absent_template_file_writes_no_template_key` | pass |
| template edited mid-ingest: pre-edit hash recorded, scan lists the source | `test_template_edited_mid_ingest_records_pre_edit_hash` (edits a tmp `article.yaml` via a wrapper around `_run_ingest_body`; `kb.compile.compiler.TEMPLATES_DIR` patched) | pass |

Attempt 2 (repair of R3 decision 1, verdict `.review/T1-KBFIX-TPLBASE.r3.1.10f9c616.json` on `3839d33`). Test commit `7dda115`; no src change.

Finding F1 (class: missing-lock-count-assertion) at `tests/test_kbfix_ingest_template_baseline.py:151`: the acceptance-3 spy recorded manifest-lock acquisitions but never asserted them, so `depth == 1` passed with extra sequential acquisitions. Repair: a shared `_ManifestSpy` counts only `pipeline.file_lock` calls whose path is `HASH_MANIFEST` and tags each save with the acquisition it ran in. The literal `_MANIFEST_LOCKS_PER_INGEST = 3` names each acquisition of one first ingest: (1) `_is_duplicate_content_locked`, the duplicate check; (2) `_clear_ingest_manifest_entry`, the pre-body clear (lock taken even when the key is absent, no save then); (3) `_commit_ingest_manifest`, the commit. The count matched the candidate without a src change, so there is no real extra acquisition.

RED = mutation run (not committed). Mutation in `_commit_ingest_manifest`: save the source hash, release the lock, then take a SECOND `file_lock(HASH_MANIFEST)` to re-read and write `_template/<type>` when absent. Result: 2 failed, 4 passed:

```
E       assert 4 == 3
E        +  where 4 = <tests.test_kbfix_ingest_template_baseline._ManifestSpy object at 0x000002E17EFC9940>.acquisitions
E       assert (4, 4) == (3, 3)
FAILED tests/test_kbfix_ingest_template_baseline.py::test_source_hash_and_template_key_land_in_one_locked_save
FAILED tests/test_kbfix_ingest_template_baseline.py::test_baseline_write_adds_no_manifest_lock_acquisition
2 failed, 4 passed in 1.56s
```

`src/kb/ingest/pipeline.py` restored from git after the run (`git diff --quiet HEAD -- src/` clean). GREEN (unmutated candidate): 6 passed.

Corrected acceptance-3 row:

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 3. source hash and `_template/article` land in one save inside one `file_lock(HASH_MANIFEST)` acquisition; no extra manifest-lock acquisition | `test_source_hash_and_template_key_land_in_one_locked_save` (exactly 3 acquisitions; the one save carrying both keys runs inside acquisition 3, the commit, and is the only save), `test_baseline_write_adds_no_manifest_lock_acquisition` (ingest that writes the baseline and ingest that finds it present: `(3, 3)`) | pass |

Acceptance 6 for attempt 2: `python scripts/verify_docs.py`: collected tests 3799, test file count 217, "docs in sync"; State line reads `3799 tests across 217 test files`; changelog entries updated to 6 tests / +6.
