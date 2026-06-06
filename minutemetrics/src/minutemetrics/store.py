from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import UTC, date, datetime, timedelta

from .db import transaction
from .schemas import (
    CompetitionCreate,
    CompetitionMembershipCreate,
    CompetitionMembershipPatch,
    CompetitionPatch,
    ExerciseSyncPayload,
    HomeAssistantLinkPatch,
    ParticipantCreate,
    ParticipantPatch,
)
from .security import generate_token, hash_token, verify_token


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso_now() -> str:
    return utcnow().isoformat()


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def row_to_participant(row: sqlite3.Row, sync_token: str | None = None) -> dict:
    data = {
        "id": row["id"],
        "display_name": row["display_name"],
        "color": row["color"],
        "active": bool(row["active"]),
        "home_assistant_user_id": row["home_assistant_user_id"],
        "home_assistant_person_entity_id": row["home_assistant_person_entity_id"],
        "created_at": parse_dt(row["created_at"]),
        "updated_at": parse_dt(row["updated_at"]),
        "last_synced_at": parse_dt(row["last_synced_at"]),
        "last_sync_device_name": row["last_sync_device_name"],
        "last_sync_app_version": row["last_sync_app_version"],
    }
    if sync_token is not None:
        data["sync_token"] = sync_token
    return data


def row_to_competition(row: sqlite3.Row, default_competition_id: str, participant_count: int = 0) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "start_date": date.fromisoformat(row["start_date"]),
        "end_date": date.fromisoformat(row["end_date"]),
        "status": row["status"],
        "timezone_policy": row["timezone_policy"],
        "created_at": parse_dt(row["created_at"]),
        "updated_at": parse_dt(row["updated_at"]),
        "participant_count": participant_count,
        "is_default": row["id"] == default_competition_id,
    }


def row_to_membership(row: sqlite3.Row, sync_token: str | None = None) -> dict:
    data = {
        "competition_id": row["competition_id"],
        "participant_id": row["participant_id"],
        "display_name": row["display_name"],
        "color": row["color"],
        "participant_display_name": row["participant_display_name"],
        "participant_color": row["participant_color"],
        "display_name_override": row["display_name_override"],
        "color_override": row["color_override"],
        "active": bool(row["active"]),
        "joined_at": parse_dt(row["joined_at"]),
        "created_at": parse_dt(row["membership_created_at"]),
        "updated_at": parse_dt(row["membership_updated_at"]),
        "last_synced_at": parse_dt(row["last_synced_at"]),
    }
    if sync_token is not None:
        data["sync_token"] = sync_token
    return data


class Store:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.ensure_existing_competition_defaults()

    def ensure_existing_competition_defaults(self) -> None:
        with transaction(self.conn):
            self._ensure_default_setting()
            default_competition_id = self.default_competition_id_or_none()
            if default_competition_id is not None:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO competition_memberships (
                      competition_id, participant_id, active, joined_at, created_at, updated_at
                    )
                    SELECT ?, id, active, created_at, created_at, updated_at
                    FROM participants
                    """,
                    (default_competition_id,),
                )

    def competition(self) -> sqlite3.Row:
        return self.get_competition_row(self.default_competition_id())

    def default_competition_id(self) -> str:
        row = self.default_competition_id_or_none()
        if row is None:
            raise KeyError("default_competition_id")
        return row

    def default_competition_id_or_none(self) -> str | None:
        self._ensure_default_setting()
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", ("default_competition_id",)).fetchone()
        return row["value"] if row is not None else None

    def _ensure_default_setting(self) -> None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", ("default_competition_id",)).fetchone()
        if row is not None and self._competition_exists(row["value"]):
            return
        fallback = self.conn.execute(
            """
            SELECT id FROM competitions
            ORDER BY
              CASE WHEN id = 'default' THEN 0 ELSE 1 END,
              CASE WHEN status = 'active' THEN 0 ELSE 1 END,
              created_at,
              id
            LIMIT 1
            """
        ).fetchone()
        if fallback is None:
            return
        was_in_transaction = self.conn.in_transaction
        self.conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            ("default_competition_id", fallback["id"]),
        )
        if not was_in_transaction:
            self.conn.commit()

    def _competition_exists(self, competition_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM competitions WHERE id = ?", (competition_id,)).fetchone()
        return row is not None

    def get_competition_row(self, competition_id: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM competitions WHERE id = ?", (competition_id,)).fetchone()
        if row is None:
            raise KeyError(competition_id)
        return row

    def get_competition_row_by_slug(self, slug: str, include_archived: bool = False) -> sqlite3.Row:
        where = "slug = ?"
        params: list[object] = [slug]
        if not include_archived:
            where += " AND status = 'active'"
        row = self.conn.execute(f"SELECT * FROM competitions WHERE {where}", params).fetchone()
        if row is None:
            raise KeyError(slug)
        return row

    def competition_response(self, competition_id: str) -> dict:
        row = self.get_competition_row(competition_id)
        return row_to_competition(row, self.default_competition_id(), self.competition_participant_count(competition_id))

    def competition_participant_count(self, competition_id: str) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM competition_memberships
            WHERE competition_id = ? AND active = 1
            """,
            (competition_id,),
        ).fetchone()
        return int(row["count"])

    def list_competitions(self, include_archived: bool = False) -> list[dict]:
        where = "" if include_archived else "WHERE c.status = 'active'"
        rows = self.conn.execute(
            f"""
            SELECT c.*, COUNT(CASE WHEN m.active = 1 THEN 1 END) AS participant_count
            FROM competitions c
            LEFT JOIN competition_memberships m ON m.competition_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.start_date DESC, c.created_at DESC, c.name
            """
        ).fetchall()
        default_competition_id = self.default_competition_id_or_none() or ""
        return [row_to_competition(row, default_competition_id, int(row["participant_count"])) for row in rows]

    def create_competition(self, payload: CompetitionCreate) -> dict:
        competition_id = str(uuid.uuid4())
        slug = payload.slug or self._unique_competition_slug(self._slugify(payload.name))
        now = iso_now()
        with transaction(self.conn):
            self.conn.execute(
                """
                INSERT INTO competitions (
                  id, name, slug, start_date, end_date, status, timezone_policy, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    competition_id,
                    payload.name,
                    slug,
                    payload.start_date.isoformat(),
                    payload.end_date.isoformat(),
                    payload.status,
                    payload.timezone_policy,
                    now,
                    now,
                ),
            )
        return self.competition_response(competition_id)

    def patch_competition(self, competition_id: str, payload: CompetitionPatch) -> dict:
        competition = self.get_competition_row(competition_id)
        updates: dict[str, object] = {}
        if payload.name is not None:
            updates["name"] = payload.name
        if payload.slug is not None:
            updates["slug"] = payload.slug
        if payload.start_date is not None:
            updates["start_date"] = payload.start_date.isoformat()
        if payload.end_date is not None:
            updates["end_date"] = payload.end_date.isoformat()
        if payload.status is not None:
            updates["status"] = payload.status
        if payload.timezone_policy is not None:
            updates["timezone_policy"] = payload.timezone_policy

        start = str(updates.get("start_date", competition["start_date"]))
        end = str(updates.get("end_date", competition["end_date"]))
        if end < start:
            raise ValueError("end_date must be on or after start_date")

        if updates:
            updates["updated_at"] = iso_now()
            assignments = ", ".join(f"{key} = ?" for key in updates)
            with transaction(self.conn):
                self.conn.execute(
                    f"UPDATE competitions SET {assignments} WHERE id = ?",
                    (*updates.values(), competition_id),
                )
        return self.competition_response(competition_id)

    def archive_competition(self, competition_id: str) -> dict:
        return self._set_competition_status(competition_id, "archived")

    def restore_competition(self, competition_id: str) -> dict:
        return self._set_competition_status(competition_id, "active")

    def _set_competition_status(self, competition_id: str, status: str) -> dict:
        self.get_competition_row(competition_id)
        with transaction(self.conn):
            self.conn.execute(
                "UPDATE competitions SET status = ?, updated_at = ? WHERE id = ?",
                (status, iso_now(), competition_id),
            )
        return self.competition_response(competition_id)

    def set_default_competition(self, competition_id: str) -> dict:
        self.get_competition_row(competition_id)
        with transaction(self.conn):
            self.conn.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                ("default_competition_id", competition_id),
            )
        return self.competition_response(competition_id)

    def list_competition_memberships(self, competition_id: str) -> list[dict]:
        self.get_competition_row(competition_id)
        rows = self.conn.execute(
            """
            SELECT
              m.competition_id,
              m.participant_id,
              COALESCE(m.display_name_override, p.display_name) AS display_name,
              COALESCE(m.color_override, p.color) AS color,
              p.display_name AS participant_display_name,
              p.color AS participant_color,
              m.display_name_override,
              m.color_override,
              m.active,
              m.joined_at,
              m.created_at AS membership_created_at,
              m.updated_at AS membership_updated_at,
              p.last_synced_at
            FROM competition_memberships m
            JOIN participants p ON p.id = m.participant_id
            WHERE m.competition_id = ?
            ORDER BY m.created_at, p.display_name
            """,
            (competition_id,),
        ).fetchall()
        return [row_to_membership(row) for row in rows]

    def get_competition_membership_row(self, competition_id: str, participant_id: str) -> sqlite3.Row:
        row = self.conn.execute(
            """
            SELECT
              m.competition_id,
              m.participant_id,
              COALESCE(m.display_name_override, p.display_name) AS display_name,
              COALESCE(m.color_override, p.color) AS color,
              p.display_name AS participant_display_name,
              p.color AS participant_color,
              m.display_name_override,
              m.color_override,
              m.active,
              m.joined_at,
              m.created_at AS membership_created_at,
              m.updated_at AS membership_updated_at,
              p.last_synced_at
            FROM competition_memberships m
            JOIN participants p ON p.id = m.participant_id
            WHERE m.competition_id = ? AND m.participant_id = ?
            """,
            (competition_id, participant_id),
        ).fetchone()
        if row is None:
            raise KeyError(participant_id)
        return row

    def add_competition_membership(self, competition_id: str, payload: CompetitionMembershipCreate) -> dict:
        self.get_competition_row(competition_id)
        participant_id = payload.participant_id
        token = None
        now = iso_now()
        with transaction(self.conn):
            if participant_id is None:
                participant_id = str(uuid.uuid4())
                token = generate_token()
                self.conn.execute(
                    """
                    INSERT INTO participants (
                      id, display_name, color, token_hash, active,
                      home_assistant_user_id, home_assistant_person_entity_id,
                      created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                    """,
                    (
                        participant_id,
                        payload.display_name,
                        payload.color,
                        hash_token(token),
                        payload.home_assistant_user_id,
                        payload.home_assistant_person_entity_id,
                        now,
                        now,
                    ),
                )
            else:
                self.get_participant(participant_id)
            self.conn.execute(
                """
                INSERT INTO competition_memberships (
                  competition_id, participant_id, display_name_override, color_override,
                  active, joined_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(competition_id, participant_id) DO UPDATE SET
                  display_name_override = excluded.display_name_override,
                  color_override = excluded.color_override,
                  active = excluded.active,
                  updated_at = excluded.updated_at
                """,
                (
                    competition_id,
                    participant_id,
                    payload.display_name_override,
                    payload.color_override,
                    1 if payload.active else 0,
                    now,
                    now,
                    now,
                ),
            )
        return row_to_membership(self.get_competition_membership_row(competition_id, participant_id), sync_token=token)

    def patch_competition_membership(
        self,
        competition_id: str,
        participant_id: str,
        payload: CompetitionMembershipPatch,
    ) -> dict:
        self.get_competition_membership_row(competition_id, participant_id)
        updates: dict[str, object | None] = {}
        if "display_name_override" in payload.model_fields_set:
            updates["display_name_override"] = payload.display_name_override
        if "color_override" in payload.model_fields_set:
            updates["color_override"] = payload.color_override
        if payload.active is not None:
            updates["active"] = 1 if payload.active else 0
        if updates:
            updates["updated_at"] = iso_now()
            assignments = ", ".join(f"{key} = ?" for key in updates)
            with transaction(self.conn):
                self.conn.execute(
                    f"UPDATE competition_memberships SET {assignments} WHERE competition_id = ? AND participant_id = ?",
                    (*updates.values(), competition_id, participant_id),
                )
        return row_to_membership(self.get_competition_membership_row(competition_id, participant_id))

    def delete_competition_membership(self, competition_id: str, participant_id: str) -> dict:
        self.get_competition_membership_row(competition_id, participant_id)
        with transaction(self.conn):
            self.conn.execute(
                "DELETE FROM competition_memberships WHERE competition_id = ? AND participant_id = ?",
                (competition_id, participant_id),
            )
        return {"competition_id": competition_id, "participant_id": participant_id, "deleted": True}

    def create_participant(self, payload: ParticipantCreate) -> dict:
        participant_id = str(uuid.uuid4())
        token = generate_token()
        now = iso_now()
        with transaction(self.conn):
            self.conn.execute(
                """
                INSERT INTO participants (
                  id, display_name, color, token_hash, active,
                  home_assistant_user_id, home_assistant_person_entity_id,
                  created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    participant_id,
                    payload.display_name,
                    payload.color,
                    hash_token(token),
                    payload.home_assistant_user_id,
                    payload.home_assistant_person_entity_id,
                    now,
                    now,
                ),
            )
            default_competition_id = self.default_competition_id_or_none()
            if default_competition_id is not None:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO competition_memberships (
                      competition_id, participant_id, active, joined_at, created_at, updated_at
                    )
                    VALUES (?, ?, 1, ?, ?, ?)
                    """,
                    (default_competition_id, participant_id, now, now, now),
                )
        return row_to_participant(self.get_participant(participant_id), sync_token=token)

    def list_participants(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM participants ORDER BY created_at, display_name").fetchall()
        return [row_to_participant(row) for row in rows]

    def get_participant(self, participant_id: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM participants WHERE id = ?", (participant_id,)).fetchone()
        if row is None:
            raise KeyError(participant_id)
        return row

    def patch_participant(self, participant_id: str, payload: ParticipantPatch) -> dict:
        self.get_participant(participant_id)
        updates: dict[str, object] = {}
        if payload.display_name is not None:
            updates["display_name"] = payload.display_name
        if payload.color is not None:
            updates["color"] = payload.color
        if payload.active is not None:
            updates["active"] = 1 if payload.active else 0
        if updates:
            updates["updated_at"] = iso_now()
            assignments = ", ".join(f"{key} = ?" for key in updates)
            with transaction(self.conn):
                self.conn.execute(
                    f"UPDATE participants SET {assignments} WHERE id = ?",
                    (*updates.values(), participant_id),
                )
        return row_to_participant(self.get_participant(participant_id))

    def delete_participant(self, participant_id: str) -> dict:
        self.get_participant(participant_id)
        with transaction(self.conn):
            self.conn.execute("DELETE FROM sync_events WHERE participant_id = ?", (participant_id,))
            self.conn.execute("DELETE FROM exercise_days WHERE participant_id = ?", (participant_id,))
            self.conn.execute("DELETE FROM participants WHERE id = ?", (participant_id,))
        return {"participant_id": participant_id, "deleted": True}

    def clear_sync_data(self) -> dict:
        with transaction(self.conn):
            exercise_days = self.conn.execute("SELECT COUNT(*) AS count FROM exercise_days").fetchone()["count"]
            sync_events = self.conn.execute("SELECT COUNT(*) AS count FROM sync_events").fetchone()["count"]
            self.conn.execute("DELETE FROM exercise_days")
            self.conn.execute("DELETE FROM sync_events")
            self.conn.execute(
                """
                UPDATE participants
                SET last_synced_at = NULL,
                    last_sync_device_name = NULL,
                    last_sync_app_version = NULL,
                    updated_at = ?
                """,
                (iso_now(),),
            )
        return {"deleted_exercise_days": int(exercise_days), "deleted_sync_events": int(sync_events)}

    def patch_home_assistant_link(self, participant_id: str, payload: HomeAssistantLinkPatch) -> dict:
        self.get_participant(participant_id)
        with transaction(self.conn):
            self.conn.execute(
                """
                UPDATE participants
                SET home_assistant_user_id = ?,
                    home_assistant_person_entity_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.home_assistant_user_id,
                    payload.home_assistant_person_entity_id,
                    iso_now(),
                    participant_id,
                ),
            )
        return row_to_participant(self.get_participant(participant_id))

    def rotate_token(self, participant_id: str) -> dict:
        self.get_participant(participant_id)
        token = generate_token()
        with transaction(self.conn):
            self.conn.execute(
                "UPDATE participants SET token_hash = ?, updated_at = ? WHERE id = ?",
                (hash_token(token), iso_now(), participant_id),
            )
        return {"participant_id": participant_id, "sync_token": token}

    def get_participant_by_token(self, token: str) -> sqlite3.Row | None:
        rows = self.conn.execute("SELECT * FROM participants WHERE active = 1").fetchall()
        for row in rows:
            if verify_token(token, row["token_hash"]):
                return row
        return None

    def sync_exercise_days(self, participant_id: str, payload: ExerciseSyncPayload) -> dict:
        self.get_participant(participant_id)
        now = iso_now()
        accepted_count = len(payload.days)
        changed_count = 0
        with transaction(self.conn):
            for item in payload.days:
                checksum = self._day_checksum(participant_id, item.date.isoformat(), item.exercise_minutes)
                existing = self.conn.execute(
                    "SELECT exercise_minutes, checksum FROM exercise_days WHERE participant_id = ? AND date = ?",
                    (participant_id, item.date.isoformat()),
                ).fetchone()
                if existing is None or existing["checksum"] != checksum:
                    changed_count += 1
                self.conn.execute(
                    """
                    INSERT INTO exercise_days (
                      participant_id, date, exercise_minutes, source, timezone_identifier,
                      synced_at, raw_unit, checksum
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(participant_id, date) DO UPDATE SET
                      exercise_minutes = excluded.exercise_minutes,
                      source = excluded.source,
                      timezone_identifier = excluded.timezone_identifier,
                      synced_at = excluded.synced_at,
                      raw_unit = excluded.raw_unit,
                      checksum = excluded.checksum
                    """,
                    (
                        participant_id,
                        item.date.isoformat(),
                        item.exercise_minutes,
                        "healthkit.appleExerciseTime",
                        payload.timezone_identifier,
                        now,
                        "min",
                        checksum,
                    ),
                )
            self.conn.execute(
                """
                UPDATE participants
                SET last_synced_at = ?, last_sync_device_name = ?,
                    last_sync_app_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    payload.device.name,
                    payload.device.app_version,
                    now,
                    participant_id,
                ),
            )
            self.conn.execute(
                """
                INSERT INTO sync_events (
                  id, participant_id, range_start_date, range_end_date, accepted_count,
                  changed_count, device_name, app_version, ios_version, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    participant_id,
                    payload.range.start_date.isoformat(),
                    payload.range.end_date.isoformat(),
                    accepted_count,
                    changed_count,
                    payload.device.name,
                    payload.device.app_version,
                    payload.device.ios_version,
                    now,
                ),
            )
        return {
            "participant_id": participant_id,
            "accepted_count": accepted_count,
            "changed_count": changed_count,
            "total_minutes": self.total_for_participant(participant_id),
            "server_timestamp": parse_dt(now),
            "competitions": self.sync_competition_summaries(participant_id),
        }

    def sync_profile(self, participant_id: str) -> dict:
        participant = self.get_participant(participant_id)
        return {
            "participant": row_to_participant(participant),
            "competitions": self.sync_competition_summaries(participant_id),
        }

    def sync_competition_summaries(self, participant_id: str) -> list[dict]:
        self.get_participant(participant_id)
        rows = self.conn.execute(
            """
            SELECT c.*
            FROM competitions c
            JOIN competition_memberships m ON m.competition_id = c.id
            WHERE m.participant_id = ?
              AND m.active = 1
              AND c.status = 'active'
            ORDER BY c.start_date DESC, c.created_at DESC, c.name
            """,
            (participant_id,),
        ).fetchall()

        summaries = []
        for competition in rows:
            state = self.competition_state(competition["id"])
            participant_state = next(
                (item for item in state["participants"] if item["id"] == participant_id),
                None,
            )
            summaries.append(
                {
                    "id": competition["id"],
                    "name": competition["name"],
                    "slug": competition["slug"],
                    "start_date": date.fromisoformat(competition["start_date"]),
                    "end_date": date.fromisoformat(competition["end_date"]),
                    "status": competition["status"],
                    "sync_start_date": date.fromisoformat(competition["start_date"]),
                    "sync_end_date": date.fromisoformat(competition["end_date"]),
                    "total_minutes": participant_state["total_minutes"] if participant_state else 0,
                    "rank": participant_state["rank"] if participant_state else None,
                }
            )
        return summaries

    def total_for_participant(self, participant_id: str, start_date: str | None = None, end_date: str | None = None) -> int:
        if start_date is not None and end_date is not None and end_date < start_date:
            return 0
        where = ["participant_id = ?"]
        params: list[object] = [participant_id]
        if start_date is not None:
            where.append("date >= ?")
            params.append(start_date)
        if end_date is not None:
            where.append("date <= ?")
            params.append(end_date)
        row = self.conn.execute(
            f"SELECT COALESCE(SUM(exercise_minutes), 0) AS total FROM exercise_days WHERE {' AND '.join(where)}",
            params,
        ).fetchone()
        return int(row["total"])

    def competition_state(self, competition_id: str | None = None, as_of_date: str | None = None) -> dict:
        competition_id = competition_id or self.default_competition_id()
        competition = self.competition()
        if competition_id != competition["id"]:
            row = self.conn.execute("SELECT * FROM competitions WHERE id = ?", (competition_id,)).fetchone()
            if row is None:
                raise KeyError(competition_id)
            competition = row
        today = as_of_date or date.today().isoformat()
        end_date = date.fromisoformat(competition["end_date"])
        start_date = date.fromisoformat(competition["start_date"])
        effective_actual_end = min(end_date, date.fromisoformat(today)).isoformat()
        total_days = max((end_date - start_date).days + 1, 1)
        elapsed_days = max((date.fromisoformat(effective_actual_end) - start_date).days + 1, 0)
        stale_before = utcnow() - timedelta(hours=36)

        participants = []
        for participant in self.conn.execute(
            """
            SELECT
              p.*,
              COALESCE(m.display_name_override, p.display_name) AS competition_display_name,
              COALESCE(m.color_override, p.color) AS competition_color
            FROM participants p
            JOIN competition_memberships m ON m.participant_id = p.id
            WHERE m.competition_id = ? AND m.active = 1 AND p.active = 1
            ORDER BY p.created_at, p.display_name
            """,
            (competition["id"],),
        ).fetchall():
            total = self.total_for_participant(participant["id"], competition["start_date"], effective_actual_end)
            today_minutes = 0
            if competition["start_date"] <= today <= competition["end_date"]:
                today_row = self.conn.execute(
                    """
                    SELECT COALESCE(SUM(exercise_minutes), 0) AS total
                    FROM exercise_days
                    WHERE participant_id = ? AND date = ?
                    """,
                    (participant["id"], today),
                ).fetchone()
                today_minutes = int(today_row["total"])
            days_synced = 0
            if effective_actual_end >= competition["start_date"]:
                days_row = self.conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM exercise_days
                    WHERE participant_id = ? AND date >= ? AND date <= ?
                    """,
                    (participant["id"], competition["start_date"], effective_actual_end),
                ).fetchone()
                days_synced = int(days_row["count"])
            synced_day_average = total / days_synced if days_synced else 0.0
            elapsed_day_average = total / elapsed_days if elapsed_days else 0.0
            last_synced_at = parse_dt(participant["last_synced_at"])
            participants.append(
                {
                    "id": participant["id"],
                    "display_name": participant["competition_display_name"],
                    "color": participant["competition_color"],
                    "active": bool(participant["active"]),
                    "home_assistant_user_id": participant["home_assistant_user_id"],
                    "home_assistant_person_entity_id": participant["home_assistant_person_entity_id"],
                    "total_minutes": total,
                    "today_minutes": today_minutes,
                    "days_synced": days_synced,
                    "average_daily_minutes": round(synced_day_average, 2),
                    "elapsed_day_average_minutes": round(elapsed_day_average, 2),
                    "projected_total": round(elapsed_day_average * total_days),
                    "last_synced_at": last_synced_at,
                    "is_stale": last_synced_at is None or last_synced_at < stale_before,
                    "rank": None,
                }
            )

        ranked = sorted(participants, key=lambda item: item["total_minutes"], reverse=True)
        for index, participant in enumerate(ranked, start=1):
            participant["rank"] = index
        leader = ranked[0] if ranked else None
        margin = 0
        if len(ranked) >= 2:
            margin = ranked[0]["total_minutes"] - ranked[1]["total_minutes"]

        return {
            "competition": {
                "id": competition["id"],
                "name": competition["name"],
                "slug": competition["slug"],
                "start_date": competition["start_date"],
                "end_date": competition["end_date"],
                "status": competition["status"],
                "timezone_policy": competition["timezone_policy"],
            },
            "as_of_date": today,
            "effective_actual_end_date": effective_actual_end,
            "participants": ranked,
            "leader": leader,
            "margin": margin,
            "daily_series": self.daily_series(competition["id"], competition["start_date"], effective_actual_end),
        }

    def daily_series(
        self,
        competition_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, list[dict[str, str | int]]]:
        if start_date is not None and end_date is not None and end_date < start_date:
            return {}
        series: dict[str, list[dict[str, str | int]]] = {}
        params: list[object] = []
        joins = ""
        where: list[str] = []
        if competition_id is not None:
            joins = "JOIN competition_memberships m ON m.participant_id = d.participant_id"
            where.append("m.competition_id = ? AND m.active = 1")
            params.append(competition_id)
        if start_date is not None:
            where.append("d.date >= ?")
            params.append(start_date)
        if end_date is not None:
            where.append("d.date <= ?")
            params.append(end_date)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self.conn.execute(
            f"""
            SELECT d.participant_id, d.date, d.exercise_minutes
            FROM exercise_days d
            {joins}
            {where_sql}
            ORDER BY d.date
            """,
            params,
        ).fetchall()
        for row in rows:
            series.setdefault(row["participant_id"], []).append(
                {"date": row["date"], "exercise_minutes": int(row["exercise_minutes"])}
            )
        return series

    def sensor_payloads(self) -> list[dict]:
        try:
            state = self.competition_state()
        except KeyError:
            return []
        payloads = []
        for participant in state["participants"]:
            base_attrs = {
                "participant_id": participant["id"],
                "display_name": participant["display_name"],
                "color": participant["color"],
                "home_assistant_user_id": participant["home_assistant_user_id"],
                "home_assistant_person_entity_id": participant["home_assistant_person_entity_id"],
                "last_synced_at": participant["last_synced_at"].isoformat() if participant["last_synced_at"] else None,
                "is_stale": participant["is_stale"],
                "rank": participant["rank"],
            }
            slug = self._slug(participant["display_name"], participant["id"])
            payloads.append(
                {
                    "entity_id": f"sensor.minutemetrics_participant_{slug}_total",
                    "state": participant["total_minutes"],
                    "attributes": {**base_attrs, "unit_of_measurement": "min"},
                }
            )
            payloads.append(
                {
                    "entity_id": f"sensor.minutemetrics_participant_{slug}_today",
                    "state": participant["today_minutes"],
                    "attributes": {**base_attrs, "unit_of_measurement": "min"},
                }
            )
        payloads.append(
            {
                "entity_id": "sensor.minutemetrics_leader",
                "state": state["leader"]["display_name"] if state["leader"] else "none",
                "attributes": {"participant_id": state["leader"]["id"] if state["leader"] else None},
            }
        )
        payloads.append(
            {
                "entity_id": "sensor.minutemetrics_margin",
                "state": state["margin"],
                "attributes": {"unit_of_measurement": "min"},
            }
        )
        return payloads

    @staticmethod
    def _day_checksum(participant_id: str, day: str, minutes: int) -> str:
        value = f"{participant_id}:{day}:{minutes}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _slug(display_name: str, participant_id: str) -> str:
        safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in display_name).strip("_")
        safe = "_".join(part for part in safe.split("_") if part)
        return f"{safe or 'participant'}_{participant_id[:8]}"

    def _unique_competition_slug(self, base: str) -> str:
        slug = base or "competition"
        candidate = slug
        suffix = 2
        while self.conn.execute("SELECT 1 FROM competitions WHERE slug = ?", (candidate,)).fetchone() is not None:
            candidate = f"{slug}-{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _slugify(value: str) -> str:
        safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
        return "-".join(part for part in safe.split("-") if part) or "competition"
