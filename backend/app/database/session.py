"""Create the local SQLite schema and provide short transactional connections."""
import sqlite3
from contextlib import contextmanager

from app.config import DATABASE_PATH


SCHEMA = """
PRAGMA foreign_keys=ON;
-- Uploaded image metadata and its moderation decision.
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, sha256 TEXT NOT NULL,
  path TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
  policy_version TEXT NOT NULL, nsfw_score REAL NOT NULL, created_at TEXT NOT NULL
);
-- Jobs hold progress while running and ordered frame metadata when complete.
CREATE TABLE IF NOT EXISTS generations (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
  request_json TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
  progress INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL,
  result_json TEXT, error_code TEXT, error_detail TEXT,
  cancel_requested INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(owner_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS generations_owner_created ON generations(owner_id, created_at DESC);
-- Export settings and file path are kept separate from the generation result.
CREATE TABLE IF NOT EXISTS exports (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, generation_id TEXT NOT NULL REFERENCES generations(id),
  status TEXT NOT NULL, format TEXT NOT NULL, settings_json TEXT NOT NULL,
  path TEXT, error_detail TEXT, created_at TEXT NOT NULL
);
"""


def initialize() -> None:
    """Create missing tables when the API starts; existing records are kept."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript(SCHEMA)


@contextmanager
def connect():
    """Commit successful database work and roll back if a query fails."""
    db = sqlite3.connect(DATABASE_PATH, timeout=30, isolation_level="IMMEDIATE")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
