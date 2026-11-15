---
id: T1-KBFIX-VECDIM
title: "`VectorIndex` reads the stored embedding dimension from the `vec_pages` declaration in `sqlite_master`, so vector search returns hits with sqlite-vec 0.1.9 (#154)"
status: todo
branch: T1-KBFIX-VECDIM
worktree: D:\wt\llm-wiki-flywheel\T1-KBFIX-VECDIM
plan_ref: plans/kb-defects-1.md#order-of-work
allow_paths:
  - src/kb/query/embeddings.py
  - tests/test_kbfix_vector_stored_dim.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T1-KBFIX-VECDIM.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_vector_stored_dim.py tests/test_cycle25_dim_mismatch.py tests/test_cycle64_dim_mismatch_autorebuild.py tests/test_cycle24_vector_atomic_rebuild.py tests/test_cycle28_first_query_observability.py -q
dod_exit: 0
requirements:
  - R1. WHEN the `vec_pages` table exists, `VectorIndex._read_stored_dim` shall return the `N` of `float[N]` in that table's declaration in `sqlite_master.sql`, whatever `PRAGMA table_info` reports.
  - R2. IF the `vec_pages` table does not exist, THEN `_read_stored_dim` shall return 0 and log no WARNING.
  - R3. IF the `vec_pages` table exists and its declaration holds no `float[N]`, THEN `_read_stored_dim` shall return 0 and the `VectorIndex` instance shall log one WARNING naming the database path, at most once per instance.
  - R4. WHEN an index is built by `VectorIndex.build` with the installed `sqlite_vec` extension and queried with a vector of the built dimension, `VectorIndex.query` shall return at least one hit.
acceptance:
  - 1. `test_kbfix_vector_stored_dim.py`, real `sqlite_vec` extension (no stub, and the test is not skipped when `sqlite_vec` imports): build 3 pages of dimension 4, query with the vector of one of them, and that page is the first hit. [R1] [R4] [dod arm 2]
  - 2. Same file: on a real `vec0` table of dimension 7, the test first asserts `PRAGMA table_info(vec_pages)` reports an empty type for `embedding` (the format this card guards), then `_read_stored_dim` returns 7. [R1] [dod arm 2]
  - 3. Same file: a missing table returns 0 with no WARNING record; a `vec_pages` table declared without `float[N]` returns 0, and two `query` calls on one instance produce exactly one WARNING record whose message holds the database path. [R2] [R3] [dod arm 2]
  - 4. The existing dim-mismatch, auto-rebuild, atomic-rebuild and first-query tests in the DoD pass with no edit to them. [dod arm 2]
  - 5. `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the test and test-file counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 200
sweep: "Six paths: one src file, one new test file, three doc files, this card. `grep -rn 'PRAGMA\\|sqlite_master' src/` finds one schema reader, `_read_stored_dim` (embeddings.py:711); the dim-mismatch and auto-rebuild code consumes its value and is not changed."
forbid: [a stub or fake of `sqlite_vec` in the R4 test, any change to the dim-mismatch or auto-rebuild behaviour, a new dependency or version pin change]
non_goals: [`KB_DISABLE_VECTORS` not applying to `search_pages` (separate defect noted in issue 154), migrating or rebuilding existing index files (the fix reads them as they are), a sqlite-vec version floor]
diagnosis:
  root_cause: "`_read_stored_dim` parsed the dimension from the `type` column of `PRAGMA table_info(vec_pages)`, a format sqlite-vec does not guarantee. With sqlite-vec 0.1.9 (SQLite 3.50.4) that column is empty for a `vec0` virtual table (reproduced 2026-11-15), so the dim read 0, and `query` treats 0 as an empty index and returns [] with no log."
  same_class: "No other reader of the vec_pages schema in src/ (grep above). The declaration is written in one place, `VectorIndex.build` (embeddings.py:686, `vec0(embedding float[{dim}])`), so `sqlite_master.sql` always holds the dim for indexes this code builds."
hygiene: "Run the DoD with the main checkout's `.venv` active. RED: the R4 and acceptance-2 tests fail on the unfixed code with an empty result / 0, not with an import or collection error."
doc_sync: CHANGELOG.md
---

# T1-KBFIX-VECDIM

## Deliverable
`VectorIndex._read_stored_dim` reads the dimension from the `vec_pages` declaration in `sqlite_master`, so the vector branch of hybrid search returns hits again with the pinned sqlite-vec 0.1.9, and a test against the real extension fails if the declaration format changes.

## Why
Issue #154. Since sqlite-vec 0.1.9 every vector query returns [] silently, so hybrid search has been BM25-only. The knowledge baseline could not measure the hybrid arm for this reason.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_vector_stored_dim.py tests/test_cycle25_dim_mismatch.py tests/test_cycle64_dim_mismatch_autorebuild.py tests/test_cycle24_vector_atomic_rebuild.py tests/test_cycle28_first_query_observability.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED commit `f321f61`, GREEN commit `57c877d`. Tests: `tests/test_kbfix_vector_stored_dim.py` (real `sqlite_vec` 0.1.9, SQLite 3.50.4, no stub).

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. build 3 pages of dim 4, query with one page's vector, that page is the first hit | `test_built_index_returns_matching_page_first` | pass |
| 2. real `vec0` table of dim 7: `PRAGMA table_info` type for `embedding` is empty, `_read_stored_dim` returns 7 | `test_stored_dim_read_from_declaration_when_pragma_type_is_empty` | pass |
| 3. missing table: 0, no WARNING; table without `float[N]`: 0, two `query` calls on one instance give exactly one WARNING holding the db path | `test_missing_table_returns_zero_without_warning`, `test_table_without_dim_warns_once_per_instance_naming_db` | pass |
| 4. existing dim-mismatch, auto-rebuild, atomic-rebuild and first-query tests pass unedited | DoD arm 2: `test_cycle25_dim_mismatch.py`, `test_cycle64_dim_mismatch_autorebuild.py`, `test_cycle24_vector_atomic_rebuild.py`, `test_cycle28_first_query_observability.py` (no edit; `git diff main -- tests/` touches only the new file) | pass |
| 5. one entry under this card id in `CHANGELOG.md` `[Unreleased]` and in `CHANGELOG-history.md`; `CLAUDE.md` State counts equal `scripts/verify_docs.py` | `python scripts/verify_docs.py`: collected tests 3789, test file count 216; `CLAUDE.md` State line reads `3789 tests across 216 test files` | pass (reviewer-verified) |

RED against the unfixed code (`main` at `640cf1b`): 3 failed, 1 passed. Failures are all `AssertionError`: `query` returned `[]` (acceptance 1), `_read_stored_dim` returned 0 for `float[7]` (acceptance 2), 0 WARNING records for a table without `float[N]` (acceptance 3, R3). No import or collection error. The 1 pass is the missing-table guard (R2), which the unfixed code already met. GREEN: DoD 32 passed.

Attempt 2 (repair of R3 decision 1, verdict `.review/T1-KBFIX-VECDIM.r3.1.db2c7dff.json` on `fcdb090`). RED commit `d33ff6a`, GREEN commit `44f2a32`.

Finding F1 (class: schema-warning-race) at `src/kb/query/embeddings.py:725`: concurrent first queries on one shared `VectorIndex` could each see `_schema_warned` False and log the R3 WARNING more than once. Same-class site in `allow_paths`: `_dim_warned` in `query()` (the dim-mismatch WARNING). Repair: one per-instance `_warn_lock`; under it, if the flag is False it is set True and the WARNING is logged. The lock covers only the flag and the log call: not the SQL query, not the auto-rebuild, never nested with `_conn_lock`. `_dim_warned` changed as a same-class site per the REVIEW_FIX directive; single-thread behaviour, the mismatch counter and auto-rebuild are unchanged.

| Input form / failure path | Covering test | Result |
|---|---|---|
| schema warning: 4 concurrent first `_read_stored_dim` calls on one instance, table without `float[N]` | `tests/test_kbfix_vector_stored_dim.py::test_schema_warning_logged_once_under_concurrent_first_reads` | pass |
| dim-mismatch warning: 4 concurrent `query` calls with a dim-3 vector on one instance of a real dim-4 index, `KB_DISABLE_VECTOR_AUTO_REBUILD=1` | `tests/test_kbfix_vector_stored_dim.py::test_dim_mismatch_warning_logged_once_under_concurrent_queries` | pass |
| single-thread paths unchanged (dim-mismatch message, per-query counter, auto-rebuild, first-query logging) | DoD arm 2: the 4 existing test files, no edit | pass |

Both tests release 4 threads on one `threading.Event` and replace `kb.query.embeddings.logger.warning` with a recorder that sleeps 0.2s, so every thread reaches the check before the first caller returns. RED on `fcdb090`: 2 failed, 4 passed; both failures `AssertionError: assert 4 == 1` (4 recorded warnings), no import or collection error. GREEN: DoD 34 passed.

Acceptance table, corrected for attempt 2:

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1 | `test_built_index_returns_matching_page_first` | pass |
| 2 | `test_stored_dim_read_from_declaration_when_pragma_type_is_empty` | pass |
| 3 | `test_missing_table_returns_zero_without_warning`, `test_table_without_dim_warns_once_per_instance_naming_db`, `test_schema_warning_logged_once_under_concurrent_first_reads` (at most once per instance under concurrency) | pass |
| 4 | DoD arm 2: `test_cycle25_dim_mismatch.py`, `test_cycle64_dim_mismatch_autorebuild.py`, `test_cycle24_vector_atomic_rebuild.py`, `test_cycle28_first_query_observability.py`, no edit (`git diff main -- tests/` touches only the new file) | pass |
| 5 | `python scripts/verify_docs.py`: collected tests 3791, test file count 216; `CLAUDE.md` State line reads `3791 tests across 216 test files`; changelog entries updated to 6 tests / +6 | pass (reviewer-verified) |
