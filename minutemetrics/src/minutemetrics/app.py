from __future__ import annotations

import sqlite3
from datetime import date
from io import BytesIO
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import qrcode
import qrcode.image.svg

from . import __version__
from .config import Settings, load_settings
from .db import connect, init_db
from .schemas import (
    AppConfigResponse,
    CompetitionCreate,
    CompetitionMembershipCreate,
    CompetitionMembershipPatch,
    CompetitionMembershipResponse,
    CompetitionPatch,
    CompetitionResponse,
    CompetitionState,
    ExerciseSyncPayload,
    HealthResponse,
    HomeAssistantLinkPatch,
    PairingQRRequest,
    ParticipantCreate,
    ParticipantCreatedResponse,
    ParticipantPatch,
    ParticipantResponse,
    SyncMeResponse,
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

    @app.middleware("http")
    async def prevent_dashboard_asset_cache(request, call_next):
        response = await call_next(request)
        if request.url.path in {"/", "/admin"} or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

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
    def dashboard() -> HTMLResponse:
        return versioned_html(static_dir / "index.html")

    @app.get("/admin", include_in_schema=False)
    def admin_dashboard() -> HTMLResponse:
        return versioned_html(static_dir / "admin.html")

    @app.get("/api/v1/app-config", response_model=AppConfigResponse)
    def app_config() -> dict:
        return {"server_url": settings.server_url}

    @app.get("/api/v1/admin/participants", response_model=list[ParticipantResponse], dependencies=[Depends(require_admin)])
    def list_participants() -> list[dict]:
        return store.list_participants()

    @app.get(
        "/api/v1/admin/competitions",
        response_model=list[CompetitionResponse],
        dependencies=[Depends(require_admin)],
    )
    def admin_list_competitions(include_archived: bool = True) -> list[dict]:
        return store.list_competitions(include_archived=include_archived)

    @app.post(
        "/api/v1/admin/competitions",
        response_model=CompetitionResponse,
        dependencies=[Depends(require_admin)],
        status_code=status.HTTP_201_CREATED,
    )
    def admin_create_competition(payload: CompetitionCreate) -> dict:
        return _store_guard(lambda: store.create_competition(payload))

    @app.get(
        "/api/v1/admin/competitions/{competition_id}",
        response_model=CompetitionResponse,
        dependencies=[Depends(require_admin)],
    )
    def admin_get_competition(competition_id: str) -> dict:
        return _store_guard(lambda: store.competition_response(competition_id), competition_id)

    @app.patch(
        "/api/v1/admin/competitions/{competition_id}",
        response_model=CompetitionResponse,
        dependencies=[Depends(require_admin)],
    )
    def admin_patch_competition(competition_id: str, payload: CompetitionPatch) -> dict:
        return _store_guard(lambda: store.patch_competition(competition_id, payload), competition_id)

    @app.post(
        "/api/v1/admin/competitions/{competition_id}/archive",
        response_model=CompetitionResponse,
        dependencies=[Depends(require_admin)],
    )
    def admin_archive_competition(competition_id: str) -> dict:
        return _store_guard(lambda: store.archive_competition(competition_id), competition_id)

    @app.post(
        "/api/v1/admin/competitions/{competition_id}/restore",
        response_model=CompetitionResponse,
        dependencies=[Depends(require_admin)],
    )
    def admin_restore_competition(competition_id: str) -> dict:
        return _store_guard(lambda: store.restore_competition(competition_id), competition_id)

    @app.post(
        "/api/v1/admin/competitions/{competition_id}/default",
        response_model=CompetitionResponse,
        dependencies=[Depends(require_admin)],
    )
    def admin_set_default_competition(competition_id: str) -> dict:
        return _store_guard(lambda: store.set_default_competition(competition_id), competition_id)

    @app.get(
        "/api/v1/admin/competitions/{competition_id}/participants",
        response_model=list[CompetitionMembershipResponse],
        dependencies=[Depends(require_admin)],
    )
    def admin_list_competition_memberships(competition_id: str) -> list[dict]:
        return _store_guard(lambda: store.list_competition_memberships(competition_id), competition_id)

    @app.post(
        "/api/v1/admin/competitions/{competition_id}/participants",
        response_model=CompetitionMembershipResponse,
        dependencies=[Depends(require_admin)],
        status_code=status.HTTP_201_CREATED,
    )
    def admin_add_competition_membership(competition_id: str, payload: CompetitionMembershipCreate) -> dict:
        return _store_guard(lambda: store.add_competition_membership(competition_id, payload), competition_id)

    @app.patch(
        "/api/v1/admin/competitions/{competition_id}/participants/{participant_id}",
        response_model=CompetitionMembershipResponse,
        dependencies=[Depends(require_admin)],
    )
    def admin_patch_competition_membership(
        competition_id: str,
        participant_id: str,
        payload: CompetitionMembershipPatch,
    ) -> dict:
        return _store_guard(
            lambda: store.patch_competition_membership(competition_id, participant_id, payload),
            participant_id,
        )

    @app.delete(
        "/api/v1/admin/competitions/{competition_id}/participants/{participant_id}",
        dependencies=[Depends(require_admin)],
    )
    def admin_delete_competition_membership(competition_id: str, participant_id: str) -> dict:
        return _store_guard(lambda: store.delete_competition_membership(competition_id, participant_id), participant_id)

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

    @app.delete("/api/v1/admin/participants/{participant_id}", dependencies=[Depends(require_admin)])
    def delete_participant(participant_id: str) -> dict:
        return _not_found_guard(lambda: store.delete_participant(participant_id), participant_id)

    @app.delete("/api/v1/admin/data", dependencies=[Depends(require_admin)])
    def clear_sync_data() -> dict:
        return store.clear_sync_data()

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

    @app.get("/api/v1/sync/me", response_model=SyncMeResponse)
    def sync_me(participant_id: str = Depends(require_participant_token)) -> dict:
        return _not_found_guard(lambda: store.sync_profile(participant_id), participant_id)

    @app.get("/api/v1/competition", response_model=CompetitionState)
    def competition_state(as_of_date: date | None = None) -> dict:
        return store.competition_state(as_of_date=as_of_date.isoformat() if as_of_date else None)

    @app.get("/api/v1/competitions", response_model=list[CompetitionResponse])
    def public_list_competitions() -> list[dict]:
        return store.list_competitions(include_archived=False)

    @app.get("/api/v1/competitions/{competition_id}/state", response_model=CompetitionState)
    def competition_state_by_id(competition_id: str, as_of_date: date | None = None) -> dict:
        return _store_guard(
            lambda: store.competition_state(
                competition_id=competition_id,
                as_of_date=as_of_date.isoformat() if as_of_date else None,
            ),
            competition_id,
        )

    @app.get("/api/v1/competitions/by-slug/{slug}/state", response_model=CompetitionState)
    def competition_state_by_slug(slug: str, as_of_date: date | None = None) -> dict:
        return _store_guard(
            lambda: store.competition_state(
                competition_id=store.get_competition_row_by_slug(slug)["id"],
                as_of_date=as_of_date.isoformat() if as_of_date else None,
            ),
            slug,
        )

    @app.get("/api/v1/home-assistant/sensors", dependencies=[Depends(require_admin)])
    def sensor_payloads() -> list[dict]:
        return store.sensor_payloads()

    return app


def _not_found_guard(callback: Callable[[], dict], resource_id: str) -> dict:
    try:
        return callback()
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Not found: {resource_id}") from None


def _store_guard(callback: Callable[[], dict], resource_id: str | None = None) -> dict:
    try:
        return callback()
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Not found: {resource_id}") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource conflict") from None


def versioned_html(path: Path) -> HTMLResponse:
    content = path.read_text(encoding="utf-8")
    for asset in ("static/styles.css", "static/app.js", "static/admin.js"):
        content = content.replace(f'"{asset}"', f'"{asset}?v={__version__}"')
    return HTMLResponse(content)


def pairing_url(server_url: str, sync_token: str) -> str:
    query = urlencode({"server_url": server_url.rstrip("/"), "sync_token": sync_token})
    return f"minutemetrics://pair?{query}"
