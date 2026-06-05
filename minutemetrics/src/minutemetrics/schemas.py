from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class DevicePayload(BaseModel):
    name: str | None = None
    app_version: str | None = None
    ios_version: str | None = None


class DateRangePayload(BaseModel):
    start_date: date
    end_date: date


class ExerciseDayPayload(BaseModel):
    date: date
    exercise_minutes: int = Field(ge=0)


class ExerciseSyncPayload(BaseModel):
    device: DevicePayload = Field(default_factory=DevicePayload)
    range: DateRangePayload
    timezone_identifier: str
    days: list[ExerciseDayPayload]


class ParticipantCreate(BaseModel):
    display_name: str = Field(min_length=1)
    color: str = Field(default="#2f80ed", min_length=1)
    home_assistant_user_id: str | None = None
    home_assistant_person_entity_id: str | None = None


class ParticipantPatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1)
    color: str | None = Field(default=None, min_length=1)
    active: bool | None = None


class HomeAssistantLinkPatch(BaseModel):
    home_assistant_user_id: str | None = None
    home_assistant_person_entity_id: str | None = None


class ParticipantResponse(BaseModel):
    id: str
    display_name: str
    color: str
    active: bool
    home_assistant_user_id: str | None
    home_assistant_person_entity_id: str | None
    created_at: datetime
    updated_at: datetime
    last_synced_at: datetime | None
    last_sync_device_name: str | None
    last_sync_app_version: str | None


class ParticipantCreatedResponse(ParticipantResponse):
    sync_token: str


class TokenRotatedResponse(BaseModel):
    participant_id: str
    sync_token: str


class AppConfigResponse(BaseModel):
    server_url: str | None = None


class PairingQRRequest(BaseModel):
    server_url: str = Field(min_length=1)
    sync_token: str = Field(min_length=1)


class SyncResponse(BaseModel):
    participant_id: str
    accepted_count: int
    changed_count: int
    total_minutes: int
    server_timestamp: datetime


class ParticipantCompetitionState(BaseModel):
    id: str
    display_name: str
    color: str
    active: bool
    home_assistant_user_id: str | None
    home_assistant_person_entity_id: str | None
    total_minutes: int
    today_minutes: int
    days_synced: int
    average_daily_minutes: float
    projected_total: int
    last_synced_at: datetime | None
    is_stale: bool
    rank: int | None


class CompetitionState(BaseModel):
    competition: dict[str, str]
    participants: list[ParticipantCompetitionState]
    leader: ParticipantCompetitionState | None
    margin: int
    daily_series: dict[str, list[dict[str, str | int]]]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
