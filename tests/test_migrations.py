from __future__ import annotations

import sqlite3

from minutemetrics.db import connect, init_db


OLD_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE competitions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  timezone_policy TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE participants (
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

CREATE TABLE exercise_days (
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

CREATE TABLE sync_events (
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

CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def old_database() -> sqlite3.Connection:
    conn = connect(":memory:")
    conn.executescript(OLD_SCHEMA)
    conn.execute(
        """
        INSERT INTO competitions (
          id, name, start_date, end_date, timezone_policy, created_at, updated_at
        )
        VALUES ('default', 'Old Minutes', '2026-01-01', '2026-12-31', 'participant_local_day',
                '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
        """
    )
    conn.execute(
        """
        INSERT INTO participants (
          id, display_name, color, token_hash, active, created_at, updated_at
        )
        VALUES ('participant-1', 'Runner One', '#28a745', 'hash-1', 1,
                '2026-01-02T00:00:00Z', '2026-01-02T00:00:00Z')
        """
    )
    conn.execute(
        """
        INSERT INTO exercise_days (
          participant_id, date, exercise_minutes, source, timezone_identifier,
          synced_at, raw_unit, checksum
        )
        VALUES ('participant-1', '2026-01-03', 42, 'healthkit.appleExerciseTime',
                'America/New_York', '2026-01-03T12:00:00Z', 'min', 'checksum-1')
        """
    )
    conn.execute(
        """
        INSERT INTO sync_events (
          id, participant_id, range_start_date, range_end_date, accepted_count,
          changed_count, created_at
        )
        VALUES ('sync-1', 'participant-1', '2026-01-03', '2026-01-03', 1, 1,
                '2026-01-03T12:00:00Z')
        """
    )
    conn.commit()
    return conn


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_init_db_creates_current_schema() -> None:
    conn = connect(":memory:")
    init_db(conn)

    assert {"slug", "status"}.issubset(column_names(conn, "competitions"))
    assert "competition_memberships" in {
        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert conn.execute("SELECT version FROM schema_migrations WHERE version = 1").fetchone() is not None


def test_migration_from_0_1_1_schema_preserves_data_and_backfills_memberships() -> None:
    conn = old_database()

    init_db(conn)
    init_db(conn)

    competition = conn.execute("SELECT * FROM competitions WHERE id = 'default'").fetchone()
    assert competition["name"] == "Old Minutes"
    assert competition["slug"] == "default"
    assert competition["status"] == "active"

    setting = conn.execute("SELECT value FROM settings WHERE key = 'default_competition_id'").fetchone()
    assert setting["value"] == "default"

    membership = conn.execute(
        """
        SELECT * FROM competition_memberships
        WHERE competition_id = 'default' AND participant_id = 'participant-1'
        """
    ).fetchone()
    assert membership is not None
    assert membership["active"] == 1

    exercise_day = conn.execute("SELECT exercise_minutes FROM exercise_days WHERE participant_id = 'participant-1'").fetchone()
    assert exercise_day["exercise_minutes"] == 42

    sync_event = conn.execute("SELECT accepted_count FROM sync_events WHERE id = 'sync-1'").fetchone()
    assert sync_event["accepted_count"] == 1

    membership_count = conn.execute("SELECT COUNT(*) AS count FROM competition_memberships").fetchone()
    assert membership_count["count"] == 1
