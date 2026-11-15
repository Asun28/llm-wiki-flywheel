"""T1-KBFIX-VECDIM (#154): the stored embedding dim comes from the `vec_pages`
declaration in `sqlite_master`, not from `PRAGMA table_info`.

These tests use the REAL `sqlite_vec` extension (a project dependency). With
sqlite-vec 0.1.9 `PRAGMA table_info(vec_pages)` reports an empty type for the
`embedding` column, so a reader that parses that column sees dim 0 and every
vector query returns [] silently.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

import sqlite_vec

import kb.query.embeddings
from kb.query.embeddings import VectorIndex

_LOGGER = "kb.query.embeddings"


def _db_path(tmp_path: Path) -> Path:
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "vector_index.db"


def _vec_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def test_built_index_returns_matching_page_first(tmp_path):
    """Acceptance 1 [R1][R4]: build 3 pages of dim 4, query with one page's vector."""
    db_path = _db_path(tmp_path)
    entries = [
        ("concepts/alpha", [1.0, 0.0, 0.0, 0.0]),
        ("concepts/beta", [0.0, 1.0, 0.0, 0.0]),
        ("concepts/gamma", [0.0, 0.0, 1.0, 0.0]),
    ]
    VectorIndex(db_path).build(entries)

    hits = VectorIndex(db_path).query([0.0, 1.0, 0.0, 0.0], limit=3)

    assert hits, "vector query returned no hits for a vector stored in the index"
    assert hits[0][0] == "concepts/beta"


def test_stored_dim_read_from_declaration_when_pragma_type_is_empty(tmp_path):
    """Acceptance 2 [R1]: a real vec0 table of dim 7 reports dim 7."""
    db_path = _db_path(tmp_path)
    conn = _vec_connection(db_path)
    try:
        conn.execute("CREATE VIRTUAL TABLE vec_pages USING vec0(embedding float[7])")
        columns = {row[1]: row[2] for row in conn.execute("PRAGMA table_info(vec_pages)")}
        # The format this card guards: the PRAGMA type column carries no dim.
        assert columns["embedding"] == ""

        assert VectorIndex(db_path)._read_stored_dim(conn) == 7
    finally:
        conn.close()


def test_missing_table_returns_zero_without_warning(tmp_path, caplog):
    """Acceptance 3 [R2]: no vec_pages table -> 0, no WARNING."""
    db_path = _db_path(tmp_path)
    conn = _vec_connection(db_path)
    try:
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            assert VectorIndex(db_path)._read_stored_dim(conn) == 0
    finally:
        conn.close()
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_table_without_dim_warns_once_per_instance_naming_db(tmp_path, caplog):
    """Acceptance 3 [R3]: vec_pages without float[N] -> 0 and exactly one WARNING."""
    db_path = _db_path(tmp_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE vec_pages (embedding BLOB)")
        conn.commit()
        assert VectorIndex(db_path)._read_stored_dim(conn) == 0
    finally:
        conn.close()

    idx = VectorIndex(db_path)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        assert idx.query([0.0, 1.0, 0.0, 0.0]) == []
        assert idx.query([0.0, 1.0, 0.0, 0.0]) == []

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert str(db_path) in warnings[0].getMessage()


_THREADS = 4


def _slow_recording_warning(calls: list[str]):
    """Replace `logger.warning`: record the message, then hold the caller ~0.2s
    so every thread released together reaches the warn-once check before the
    first caller can set the flag."""

    def warning(msg, *args, **kwargs):
        calls.append(msg % args if args else msg)
        time.sleep(0.2)

    return warning


def _run_together(target) -> None:
    """Start _THREADS threads that wait on one Event, release them at once,
    and join them with a timeout (an Event, not a reusable Barrier: FW-3)."""
    go = threading.Event()
    errors: list[BaseException] = []

    def worker():
        go.wait(5)
        try:
            target()
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(_THREADS)]
    for thread in threads:
        thread.start()
    go.set()
    for thread in threads:
        thread.join(10)
    assert not any(thread.is_alive() for thread in threads)
    assert errors == []


def test_schema_warning_logged_once_under_concurrent_first_reads(tmp_path, monkeypatch):
    """R3, repair F1: concurrent reads on one instance log the schema WARNING once."""
    db_path = _db_path(tmp_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE vec_pages (embedding BLOB)")
        conn.commit()
    finally:
        conn.close()
    calls: list[str] = []
    monkeypatch.setattr(kb.query.embeddings.logger, "warning", _slow_recording_warning(calls))
    idx = VectorIndex(db_path)
    results: list[int] = []

    def read_dim():
        thread_conn = sqlite3.connect(str(db_path))
        try:
            results.append(idx._read_stored_dim(thread_conn))
        finally:
            thread_conn.close()

    _run_together(read_dim)

    assert results == [0] * _THREADS
    assert len(calls) == 1


def test_dim_mismatch_warning_logged_once_under_concurrent_queries(tmp_path, monkeypatch):
    """Same-class site of F1: concurrent mismatched queries log the dim WARNING once."""
    monkeypatch.setenv("KB_DISABLE_VECTOR_AUTO_REBUILD", "1")
    db_path = _db_path(tmp_path)
    VectorIndex(db_path).build(
        [("concepts/alpha", [1.0, 0.0, 0.0, 0.0]), ("concepts/beta", [0.0, 1.0, 0.0, 0.0])]
    )
    calls: list[str] = []
    monkeypatch.setattr(kb.query.embeddings.logger, "warning", _slow_recording_warning(calls))
    idx = VectorIndex(db_path)
    results: list[list] = []

    _run_together(lambda: results.append(idx.query([1.0, 0.0, 0.0])))

    assert results == [[]] * _THREADS
    assert len(calls) == 1


def test_trigger_named_vec_pages_does_not_supply_the_dim(tmp_path):
    """R1, repair attempt 3: only the table declaration counts, not a trigger
    of the same name whose SQL holds another float[N] and sorts first."""
    db_path = _db_path(tmp_path)
    conn = _vec_connection(db_path)
    try:
        conn.execute("CREATE TABLE helper (x)")
        conn.execute("CREATE TRIGGER vec_pages AFTER INSERT ON helper BEGIN SELECT 'float[9]'; END")
        conn.execute("CREATE VIRTUAL TABLE vec_pages USING vec0(embedding float[7])")

        assert VectorIndex(db_path)._read_stored_dim(conn) == 7
    finally:
        conn.close()


def test_view_named_vec_pages_counts_as_missing_table(tmp_path, caplog):
    """R2, repair attempt 3: a view named vec_pages is not the table -> 0, no WARNING."""
    db_path = _db_path(tmp_path)
    conn = _vec_connection(db_path)
    try:
        conn.execute("CREATE VIEW vec_pages AS SELECT 'float[9]' AS embedding")
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            assert VectorIndex(db_path)._read_stored_dim(conn) == 0
    finally:
        conn.close()
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
