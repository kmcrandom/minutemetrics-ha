from __future__ import annotations

import sqlite3
from datetime import date

from fastapi.testclient import TestClient

from minutemetrics.app import create_app, pairing_url
from minutemetrics.config import Settings
from minutemetrics.db import connect


ADMIN_TOKEN = "test-admin-token"


def client() -> TestClient:
    conn = connect(":memory:")
    app = create_app(
        Settings(db_path=":memory:", admin_token=ADMIN_TOKEN, competition_name="Test Minutes"),
        conn=conn,
    )
    return TestClient(app)


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def create_participant(api: TestClient, display_name: str = "Participant") -> dict:
    response = api.post(
        "/api/v1/admin/participants",
        headers=admin_headers(),
        json={"display_name": display_name, "color": "#28a745"},
    )
    assert response.status_code == 201
    return response.json()


def sync_payload(minutes: int = 30) -> dict:
    return {
        "device": {
            "name": "Participant iPhone",
            "app_version": "1.0.0",
            "ios_version": "18.0",
        },
        "range": {
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
        },
        "timezone_identifier": "America/New_York",
        "days": [
            {"date": "2026-01-01", "exercise_minutes": minutes},
            {"date": "2026-01-02", "exercise_minutes": 10},
        ],
    }


def test_health() -> None:
    api = client()
    response = api.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_configured_competition_metadata() -> None:
    conn = connect(":memory:")
    app = create_app(
        Settings(
            db_path=":memory:",
            admin_token=ADMIN_TOKEN,
            competition_name="Configured Minutes",
            competition_start_date="2026-02-01",
            competition_end_date="2026-11-30",
        ),
        conn=conn,
    )
    api = TestClient(app)

    response = api.get("/api/v1/competition")

    assert response.status_code == 200
    assert response.json()["competition"]["name"] == "Configured Minutes"
    assert response.json()["competition"]["start_date"] == "2026-02-01"
    assert response.json()["competition"]["end_date"] == "2026-11-30"


def test_app_config_exposes_pairing_server_url() -> None:
    conn = connect(":memory:")
    app = create_app(
        Settings(
            db_path=":memory:",
            admin_token=ADMIN_TOKEN,
            competition_name="Test Minutes",
            server_url="https://minutemetrics.example.test",
        ),
        conn=conn,
    )
    api = TestClient(app)

    response = api.get("/api/v1/app-config")

    assert response.status_code == 200
    assert response.json()["server_url"] == "https://minutemetrics.example.test"


def test_dashboard_assets_are_served() -> None:
    api = client()

    page = api.get("/")
    assert page.status_code == 200
    assert "MinuteMetrics" in page.text
    assert "static/app.js" in page.text
    assert "No exercise minutes yet" in page.text

    script = api.get("/static/app.js")
    assert script.status_code == 200
    assert "api/v1/competition" in script.text


def test_admin_token_required() -> None:
    api = client()
    response = api.get("/api/v1/admin/participants")
    assert response.status_code == 401


def test_create_participant_with_optional_home_assistant_links() -> None:
    api = client()
    response = api.post(
        "/api/v1/admin/participants",
        headers=admin_headers(),
        json={
            "display_name": "Runner One",
            "color": "#cc3366",
            "home_assistant_user_id": "ha-user-1",
            "home_assistant_person_entity_id": "person.runner_one",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "Runner One"
    assert body["home_assistant_user_id"] == "ha-user-1"
    assert body["home_assistant_person_entity_id"] == "person.runner_one"
    assert body["sync_token"]


def test_pairing_url_and_qr_generation() -> None:
    api = client()
    participant = create_participant(api)

    setup_url = pairing_url("https://minutemetrics.example.test/", participant["sync_token"])
    assert setup_url.startswith("minutemetrics://pair?")
    assert "server_url=https%3A%2F%2Fminutemetrics.example.test" in setup_url
    assert "sync_token=" in setup_url

    response = api.post(
        "/api/v1/admin/pairing-qr",
        headers=admin_headers(),
        json={
            "server_url": "https://minutemetrics.example.test",
            "sync_token": participant["sync_token"],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in response.content


def test_home_assistant_link_can_be_changed_and_cleared_without_losing_data() -> None:
    api = client()
    participant = create_participant(api, "Runner")
    participant_id = participant["id"]

    sync = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json=sync_payload(minutes=45),
    )
    assert sync.status_code == 200
    assert sync.json()["participant_id"] == participant_id
    assert sync.json()["total_minutes"] == 55

    linked = api.patch(
        f"/api/v1/admin/participants/{participant_id}/home-assistant-link",
        headers=admin_headers(),
        json={
            "home_assistant_user_id": "ha-user-2",
            "home_assistant_person_entity_id": "person.runner",
        },
    )
    assert linked.status_code == 200
    assert linked.json()["home_assistant_user_id"] == "ha-user-2"

    cleared = api.patch(
        f"/api/v1/admin/participants/{participant_id}/home-assistant-link",
        headers=admin_headers(),
        json={
            "home_assistant_user_id": None,
            "home_assistant_person_entity_id": None,
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["home_assistant_user_id"] is None

    state = api.get("/api/v1/competition").json()
    assert state["participants"][0]["total_minutes"] == 55


def test_sync_requires_participant_token_and_upserts_days() -> None:
    api = client()
    participant = create_participant(api)
    participant_id = participant["id"]

    unauthorized = api.post("/api/v1/sync/exercise-days", json=sync_payload())
    assert unauthorized.status_code == 401

    first = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json=sync_payload(minutes=30),
    )
    assert first.status_code == 200
    assert first.json()["accepted_count"] == 2
    assert first.json()["changed_count"] == 2
    assert first.json()["total_minutes"] == 40

    repeated = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json=sync_payload(minutes=30),
    )
    assert repeated.status_code == 200
    assert repeated.json()["changed_count"] == 0
    assert repeated.json()["total_minutes"] == 40

    updated = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json=sync_payload(minutes=35),
    )
    assert updated.status_code == 200
    assert updated.json()["changed_count"] == 1
    assert updated.json()["total_minutes"] == 45


def test_competition_ranking_and_sensor_payloads() -> None:
    api = client()
    first = create_participant(api, "Runner One")
    second = create_participant(api, "Runner Two")

    for participant, minutes in [(first, 60), (second, 35)]:
        response = api.post(
            "/api/v1/sync/exercise-days",
            headers={"Authorization": f"Bearer {participant['sync_token']}"},
            json=sync_payload(minutes=minutes),
        )
        assert response.status_code == 200

    state = api.get("/api/v1/competition").json()
    assert state["leader"]["id"] == first["id"]
    assert state["margin"] == 25
    assert [p["rank"] for p in state["participants"]] == [1, 2]

    sensors = api.get("/api/v1/home-assistant/sensors", headers=admin_headers())
    assert sensors.status_code == 200
    entity_ids = {item["entity_id"] for item in sensors.json()}
    assert "sensor.minutemetrics_leader" in entity_ids
    assert "sensor.minutemetrics_margin" in entity_ids


def test_rotate_token_invalidates_previous_token() -> None:
    api = client()
    participant = create_participant(api)
    participant_id = participant["id"]

    rotated = api.post(
        f"/api/v1/admin/participants/{participant_id}/rotate-token",
        headers=admin_headers(),
    )
    assert rotated.status_code == 200
    new_token = rotated.json()["sync_token"]

    old_sync = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json=sync_payload(),
    )
    assert old_sync.status_code == 401

    new_sync = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {new_token}"},
        json=sync_payload(),
    )
    assert new_sync.status_code == 200
