from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


CompetitionStatus = Literal["active", "archived"]


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
    competitions: list["SyncCompetitionSummary"] = Field(default_factory=list)


class CompetitionCreate(BaseModel):
    name: str = Field(min_length=1)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    start_date: date
    end_date: date
    status: CompetitionStatus = "active"
    timezone_policy: str = Field(default="participant_local_day", min_length=1)

    @model_validator(mode="after")
    def valid_date_range(self) -> "CompetitionCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class CompetitionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    start_date: date | None = None
    end_date: date | None = None
    status: CompetitionStatus | None = None
    timezone_policy: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def valid_date_range(self) -> "CompetitionPatch":
        if self.start_date is not None and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class CompetitionResponse(BaseModel):
    id: str
    name: str
    slug: str
    start_date: date
    end_date: date
    status: CompetitionStatus
    timezone_policy: str
    created_at: datetime
    updated_at: datetime
    participant_count: int
    is_default: bool


class CompetitionMembershipCreate(BaseModel):
    participant_id: str | None = None
    display_name: str | None = Field(default=None, min_length=1)
    color: str = Field(default="#2f80ed", min_length=1)
    home_assistant_user_id: str | None = None
    home_assistant_person_entity_id: str | None = None
    display_name_override: str | None = Field(default=None, min_length=1)
    color_override: str | None = Field(default=None, min_length=1)
    active: bool = True

    @model_validator(mode="after")
    def participant_or_name_required(self) -> "CompetitionMembershipCreate":
        if self.participant_id is None and self.display_name is None:
            raise ValueError("display_name is required when participant_id is not provided")
        return self


class CompetitionMembershipPatch(BaseModel):
    display_name_override: str | None = Field(default=None, min_length=1)
    color_override: str | None = Field(default=None, min_length=1)
    active: bool | None = None


class CompetitionMembershipResponse(BaseModel):
    competition_id: str
    participant_id: str
    display_name: str
    color: str
    participant_display_name: str
    participant_color: str
    display_name_override: str | None
    color_override: str | None
    active: bool
    joined_at: datetime
    created_at: datetime
    updated_at: datetime
    last_synced_at: datetime | None
    sync_token: str | None = None


class SyncCompetitionSummary(BaseModel):
    id: str
    name: str
    slug: str
    start_date: date
    end_date: date
    status: CompetitionStatus
    sync_start_date: date
    sync_end_date: date
    total_minutes: int
    rank: int | None


class SyncMeResponse(BaseModel):
    participant: ParticipantResponse
    competitions: list[SyncCompetitionSummary]


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
    elapsed_day_average_minutes: float
    projected_total: int
    last_synced_at: datetime | None
    is_stale: bool
    rank: int | None


class CompetitionState(BaseModel):
    competition: dict[str, str]
    as_of_date: str
    effective_actual_end_date: str
    participants: list[ParticipantCompetitionState]
    leader: ParticipantCompetitionState | None
    margin: int
    daily_series: dict[str, list[dict[str, str | int]]]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
