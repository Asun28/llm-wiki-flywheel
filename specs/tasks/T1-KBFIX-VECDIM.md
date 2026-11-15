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
