from __future__ import annotations

import sqlite3
from io import BytesIO
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import qrcode
import qrcode.image.svg

from . import __version__
from .config import Settings, load_settings
from .db import connect, init_db
from .schemas import (
    AppConfigResponse,
    CompetitionState,
    ExerciseSyncPayload,
    HealthResponse,
    HomeAssistantLinkPatch,
    PairingQRRequest,
    ParticipantCreate,
    ParticipantCreatedResponse,
    ParticipantPatch,
    ParticipantResponse,
    SyncResponse,
    TokenRotatedResponse,
)
from .store import Store


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def create_app(settings: Settings | None = None, conn: sqlite3.Connection | None = None) -> FastAPI:
    settings = settings or load_settings()
    db_conn = conn or connect(settings.db_path)
    init_db(db_conn)
    store = Store(
        db_conn,
        settings.competition_name,
        start_date=settings.competition_start_date,
        end_date=settings.competition_end_date,
    )

    app = FastAPI(title="MinuteMetrics", version=__version__)
    app.state.store = store
    app.state.settings = settings

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    def require_admin(authorization: str | None = Header(default=None)) -> None:
        token = bearer_token(authorization)
        if token != settings.admin_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")

    def require_participant_token(authorization: str | None = Header(default=None)) -> str:
        token = bearer_token(authorization)
        participant = store.get_participant_by_token(token) if token is not None else None
        if participant is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid participant token")
        return participant["id"]

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/v1/app-config", response_model=AppConfigResponse)
    def app_config() -> dict:
        return {"server_url": settings.server_url}

    @app.get("/api/v1/admin/participants", response_model=list[ParticipantResponse], dependencies=[Depends(require_admin)])
    def list_participants() -> list[dict]:
        return store.list_participants()

    @app.post(
        "/api/v1/admin/participants",
        response_model=ParticipantCreatedResponse,
        dependencies=[Depends(require_admin)],
        status_code=status.HTTP_201_CREATED,
    )
    def create_participant(payload: ParticipantCreate) -> dict:
        return store.create_participant(payload)

    @app.patch(
        "/api/v1/admin/participants/{participant_id}",
        response_model=ParticipantResponse,
        dependencies=[Depends(require_admin)],
    )
    def patch_participant(participant_id: str, payload: ParticipantPatch) -> dict:
        return _not_found_guard(lambda: store.patch_participant(participant_id, payload), participant_id)

    @app.patch(
        "/api/v1/admin/participants/{participant_id}/home-assistant-link",
        response_model=ParticipantResponse,
        dependencies=[Depends(require_admin)],
    )
    def patch_home_assistant_link(participant_id: str, payload: HomeAssistantLinkPatch) -> dict:
        return _not_found_guard(lambda: store.patch_home_assistant_link(participant_id, payload), participant_id)

    @app.post(
        "/api/v1/admin/participants/{participant_id}/rotate-token",
        response_model=TokenRotatedResponse,
        dependencies=[Depends(require_admin)],
    )
    def rotate_token(participant_id: str) -> dict:
        return _not_found_guard(lambda: store.rotate_token(participant_id), participant_id)

    @app.post("/api/v1/admin/pairing-qr", dependencies=[Depends(require_admin)])
    def pairing_qr(payload: PairingQRRequest) -> Response:
        setup_url = pairing_url(payload.server_url, payload.sync_token)
        image = qrcode.make(setup_url, image_factory=qrcode.image.svg.SvgPathImage)
        output = BytesIO()
        image.save(output)
        return Response(content=output.getvalue(), media_type="image/svg+xml")

    @app.post(
        "/api/v1/sync/exercise-days",
        response_model=SyncResponse,
    )
    def sync_exercise_days(payload: ExerciseSyncPayload, participant_id: str = Depends(require_participant_token)) -> dict:
        return _not_found_guard(lambda: store.sync_exercise_days(participant_id, payload), participant_id)

    @app.get("/api/v1/competition", response_model=CompetitionState)
    def competition_state() -> dict:
        return store.competition_state()

    @app.get("/api/v1/home-assistant/sensors", dependencies=[Depends(require_admin)])
    def sensor_payloads() -> list[dict]:
        return store.sensor_payloads()

    return app


def _not_found_guard(callback: Callable[[], dict], resource_id: str) -> dict:
    try:
        return callback()
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Not found: {resource_id}") from None


def pairing_url(server_url: str, sync_token: str) -> str:
    query = urlencode({"server_url": server_url.rstrip("/"), "sync_token": sync_token})
    return f"minutemetrics://pair?{query}"
