import sqlite3
from pathlib import Path

DB_PATH = Path("gridwatch.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                deadline    TEXT NOT NULL,
                urgency     INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'queued',
                scheduled_for TEXT,
                ran_at      TEXT,
                forecast_gco2 REAL,
                actual_gco2   REAL,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        """)
