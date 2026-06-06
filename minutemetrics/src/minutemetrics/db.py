from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS competitions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  timezone_policy TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS participants (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  color TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  home_assistant_user_id TEXT,
  home_assistant_person_entity_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_synced_at TEXT,
  last_sync_device_name TEXT,
  last_sync_app_version TEXT
);

CREATE TABLE IF NOT EXISTS exercise_days (
  participant_id TEXT NOT NULL,
  date TEXT NOT NULL,
  exercise_minutes INTEGER NOT NULL,
  source TEXT NOT NULL,
  timezone_identifier TEXT NOT NULL,
  synced_at TEXT NOT NULL,
  raw_unit TEXT NOT NULL,
  checksum TEXT NOT NULL,
  PRIMARY KEY (participant_id, date),
  FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sync_events (
  id TEXT PRIMARY KEY,
  participant_id TEXT NOT NULL,
  range_start_date TEXT NOT NULL,
  range_end_date TEXT NOT NULL,
  accepted_count INTEGER NOT NULL,
  changed_count INTEGER NOT NULL,
  device_name TEXT,
  app_version TEXT,
  ios_version TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS competition_memberships (
  competition_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  display_name_override TEXT,
  color_override TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  joined_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (competition_id, participant_id),
  FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE CASCADE,
  FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
);

"""


MIGRATIONS = (1,)


def connect(db_path: str) -> sqlite3.Connection:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _run_migrations(conn)
    conn.commit()


def _run_migrations(conn: sqlite3.Connection) -> None:
    for version in MIGRATIONS:
        if _migration_applied(conn, version):
            continue
        with transaction(conn):
            _apply_migration(conn, version)


def _migration_applied(conn: sqlite3.Connection, version: int) -> bool:
    row = conn.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone()
    return row is not None


def _apply_migration(conn: sqlite3.Connection, version: int) -> None:
    if version == 1:
        _migration_1(conn)
    else:
        raise ValueError(f"Unknown migration version: {version}")
    conn.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
        (version,),
    )


def _migration_1(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "competitions", "slug"):
        conn.execute("ALTER TABLE competitions ADD COLUMN slug TEXT")
    if not _column_exists(conn, "competitions", "status"):
        conn.execute("ALTER TABLE competitions ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS competition_memberships (
          competition_id TEXT NOT NULL,
          participant_id TEXT NOT NULL,
          display_name_override TEXT,
          color_override TEXT,
          active INTEGER NOT NULL DEFAULT 1,
          joined_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (competition_id, participant_id),
          FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE CASCADE,
          FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
        );

        UPDATE competitions
        SET slug = id
        WHERE slug IS NULL OR slug = '';

        UPDATE competitions
        SET status = 'active'
        WHERE status IS NULL OR status = '';

        INSERT OR IGNORE INTO competition_memberships (
          competition_id, participant_id, active, joined_at, created_at, updated_at
        )
        SELECT 'default', id, active, created_at, created_at, updated_at
        FROM participants
        WHERE EXISTS (SELECT 1 FROM competitions WHERE id = 'default');

        INSERT OR IGNORE INTO settings (key, value)
        SELECT 'default_competition_id', 'default'
        WHERE EXISTS (SELECT 1 FROM competitions WHERE id = 'default');

        CREATE UNIQUE INDEX IF NOT EXISTS idx_competitions_slug
          ON competitions(slug);

        CREATE INDEX IF NOT EXISTS idx_memberships_participant_id
          ON competition_memberships(participant_id);

        CREATE INDEX IF NOT EXISTS idx_memberships_competition_active
          ON competition_memberships(competition_id, active);
        """
    )


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
