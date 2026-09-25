"""Role 3 — backend: SQLite store."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "drift.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT DEFAULT (datetime('now')), n INTEGER, scenario TEXT);
CREATE TABLE IF NOT EXISTS drift_scores(batch_id INTEGER, psi_global REAL, severity TEXT, top_feature TEXT);
CREATE TABLE IF NOT EXISTS feature_scores(batch_id INTEGER, feature TEXT, psi REAL);
"""


def conn():
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    return c
