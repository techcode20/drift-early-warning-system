"""SQLite time-series store for drift scores.

The DB path is resolved per-call from the DRIFT_DB env var so tests can
point at a temp file without touching the real database:

    DRIFT_DB=/tmp/test.db uvicorn backend.main:app
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now')),
    n INTEGER NOT NULL,
    scenario TEXT NOT NULL DEFAULT 'live'
);
CREATE TABLE IF NOT EXISTS drift_scores(
    batch_id INTEGER PRIMARY KEY REFERENCES batches(id) ON DELETE CASCADE,
    psi_global REAL NOT NULL,
    severity TEXT NOT NULL,
    top_feature TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS feature_scores(
    batch_id INTEGER REFERENCES batches(id) ON DELETE CASCADE,
    feature TEXT NOT NULL,
    psi REAL NOT NULL,
    PRIMARY KEY (batch_id, feature)
);
CREATE INDEX IF NOT EXISTS idx_batches_id ON batches(id);
"""


def db_path() -> Path:
    return Path(os.environ.get("DRIFT_DB", Path(__file__).resolve().parent / "drift.db"))


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


@contextmanager
def conn():
    """Yield a connection with schema ensured; commits on success, closes always."""
    c = sqlite3.connect(db_path())
    try:
        c.execute("PRAGMA foreign_keys = ON")
        c.executescript(SCHEMA)
        yield c
        c.commit()
    finally:
        c.close()
