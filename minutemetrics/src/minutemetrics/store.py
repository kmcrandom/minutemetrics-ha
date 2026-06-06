from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import UTC, date, datetime, timedelta

from .db import transaction
from .schemas import (
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
    return datetime.fromisoformat(value) if value else None


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


class Store:
    def __init__(
        self,
        conn: sqlite3.Connection,
        competition_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        self.conn = conn
        self.competition_name = competition_name
        self.configured_start_date = start_date
        self.configured_end_date = end_date
        self.ensure_default_competition()

    def ensure_default_competition(self) -> None:
        current_year = date.today().year
        start = self.configured_start_date or date(current_year, 1, 1).isoformat()
        end = self.configured_end_date or date(current_year, 12, 31).isoformat()
        now = iso_now()
        with transaction(self.conn):
            self.conn.execute(
                """
                INSERT INTO competitions
                  (id, name, start_date, end_date, timezone_policy, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  name = excluded.name,
                  start_date = excluded.start_date,
                  end_date = excluded.end_date,
                  updated_at = excluded.updated_at
                """,
                ("default", self.competition_name, start, end, "participant_local_day", now, now),
            )

    def competition(self) -> sqlite3.Row:
        return self.conn.execute("SELECT * FROM competitions WHERE id = ?", ("default",)).fetchone()

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
        }

    def total_for_participant(self, participant_id: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(exercise_minutes), 0) AS total FROM exercise_days WHERE participant_id = ?",
            (participant_id,),
        ).fetchone()
        return int(row["total"])

    def competition_state(self) -> dict:
        competition = self.competition()
        today = date.today().isoformat()
        end_date = date.fromisoformat(competition["end_date"])
        start_date = date.fromisoformat(competition["start_date"])
        total_days = max((end_date - start_date).days + 1, 1)
        stale_before = utcnow() - timedelta(hours=36)

        participants = []
        for participant in self.conn.execute("SELECT * FROM participants ORDER BY created_at, display_name").fetchall():
            total = self.total_for_participant(participant["id"])
            today_row = self.conn.execute(
                """
                SELECT COALESCE(SUM(exercise_minutes), 0) AS total
                FROM exercise_days
                WHERE participant_id = ? AND date = ?
                """,
                (participant["id"], today),
            ).fetchone()
            days_row = self.conn.execute(
                "SELECT COUNT(*) AS count FROM exercise_days WHERE participant_id = ?",
                (participant["id"],),
            ).fetchone()
            days_synced = int(days_row["count"])
            last_synced_at = parse_dt(participant["last_synced_at"])
            average = total / days_synced if days_synced else 0.0
            participants.append(
                {
                    "id": participant["id"],
                    "display_name": participant["display_name"],
                    "color": participant["color"],
                    "active": bool(participant["active"]),
                    "home_assistant_user_id": participant["home_assistant_user_id"],
                    "home_assistant_person_entity_id": participant["home_assistant_person_entity_id"],
                    "total_minutes": total,
                    "today_minutes": int(today_row["total"]),
                    "days_synced": days_synced,
                    "average_daily_minutes": round(average, 2),
                    "projected_total": round(average * total_days),
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
                "start_date": competition["start_date"],
                "end_date": competition["end_date"],
                "timezone_policy": competition["timezone_policy"],
            },
            "participants": ranked,
            "leader": leader,
            "margin": margin,
            "daily_series": self.daily_series(),
        }

    def daily_series(self) -> dict[str, list[dict[str, str | int]]]:
        series: dict[str, list[dict[str, str | int]]] = {}
        rows = self.conn.execute(
            "SELECT participant_id, date, exercise_minutes FROM exercise_days ORDER BY date"
        ).fetchall()
        for row in rows:
            series.setdefault(row["participant_id"], []).append(
                {"date": row["date"], "exercise_minutes": int(row["exercise_minutes"])}
            )
        return series

    def sensor_payloads(self) -> list[dict]:
        state = self.competition_state()
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
