from __future__ import annotations

import sqlite3
from datetime import date

from fastapi.testclient import TestClient

from minutemetrics import __version__
from minutemetrics.app import create_app, pairing_url
from minutemetrics.config import Settings
from minutemetrics.db import connect


ADMIN_TOKEN = "test-admin-token"


def client(create_default_competition: bool = True) -> TestClient:
    conn = connect(":memory:")
    app = create_app(
        Settings(db_path=":memory:", admin_token=ADMIN_TOKEN),
        conn=conn,
    )
    api = TestClient(app)
    if create_default_competition:
        create_competition(
            api,
            name="Test Minutes",
            slug="test-minutes",
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
    return api


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


def create_competition(
    api: TestClient,
    name: str = "February Minutes",
    slug: str = "february-minutes",
    start_date: str = "2026-02-01",
    end_date: str = "2026-02-28",
) -> dict:
    response = api.post(
        "/api/v1/admin/competitions",
        headers=admin_headers(),
        json={
            "name": name,
            "slug": slug,
            "start_date": start_date,
            "end_date": end_date,
        },
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


def test_fresh_install_starts_without_competitions() -> None:
    api = client(create_default_competition=False)

    competitions = api.get("/api/v1/competitions")
    assert competitions.status_code == 200
    assert competitions.json() == []

    state = api.get("/api/v1/competition")
    assert state.status_code == 404

    sensors = api.get("/api/v1/home-assistant/sensors", headers=admin_headers())
    assert sensors.status_code == 200
    assert sensors.json() == []

    participant = create_participant(api, "Unassigned Runner")
    assert participant["display_name"] == "Unassigned Runner"

    sync = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json=sync_payload(minutes=20),
    )
    assert sync.status_code == 200
    assert sync.json()["total_minutes"] == 30
    assert sync.json()["competitions"] == []

    competition = create_competition(api, name="Configured Minutes", slug="configured-minutes")
    assert competition["name"] == "Configured Minutes"
    assert competition["is_default"] is True


def test_existing_competition_survives_app_restart() -> None:
    conn = connect(":memory:")
    app = create_app(Settings(db_path=":memory:", admin_token=ADMIN_TOKEN), conn=conn)
    api = TestClient(app)
    create_competition(
        api,
        name="Original Minutes",
        slug="original-minutes",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )

    restarted = create_app(Settings(db_path=":memory:", admin_token=ADMIN_TOKEN), conn=conn)
    restarted_api = TestClient(restarted)
    response = restarted_api.get("/api/v1/competition")

    assert response.status_code == 200
    assert response.json()["competition"]["name"] == "Original Minutes"
    assert response.json()["competition"]["start_date"] == "2026-01-01"
    assert response.json()["competition"]["end_date"] == "2026-12-31"


def test_app_config_exposes_pairing_server_url() -> None:
    conn = connect(":memory:")
    app = create_app(
        Settings(
            db_path=":memory:",
            admin_token=ADMIN_TOKEN,
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
    assert page.headers["cache-control"] == "no-store"
    assert "MinuteMetrics" in page.text
    assert f"static/styles.css?v={__version__}" in page.text
    assert f"static/app.js?v={__version__}" in page.text
    assert "No exercise minutes yet" in page.text
    assert "participantForm" not in page.text

    admin_page = api.get("/admin")
    assert admin_page.status_code == 200
    assert admin_page.headers["cache-control"] == "no-store"
    assert "Admin token" in admin_page.text
    assert f"static/styles.css?v={__version__}" in admin_page.text
    assert f"static/admin.js?v={__version__}" in admin_page.text

    script = api.get("/static/app.js")
    assert script.status_code == 200
    assert script.headers["cache-control"] == "no-store"
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


def test_admin_can_update_and_delete_participant() -> None:
    api = client()
    participant = create_participant(api, "Runner")

    updated = api.patch(
        f"/api/v1/admin/participants/{participant['id']}",
        headers=admin_headers(),
        json={"display_name": "Runner Prime", "color": "#ff8800"},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Runner Prime"
    assert updated.json()["color"] == "#ff8800"

    deleted = api.delete(f"/api/v1/admin/participants/{participant['id']}", headers=admin_headers())
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    participants = api.get("/api/v1/admin/participants", headers=admin_headers())
    assert participants.status_code == 200
    assert participants.json() == []


def test_admin_can_clear_sync_data_without_deleting_participants() -> None:
    api = client()
    participant = create_participant(api, "Runner")
    sync = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json=sync_payload(minutes=45),
    )
    assert sync.status_code == 200

    cleared = api.delete("/api/v1/admin/data", headers=admin_headers())
    assert cleared.status_code == 200
    assert cleared.json()["deleted_exercise_days"] == 2
    assert cleared.json()["deleted_sync_events"] == 1

    state = api.get("/api/v1/competition").json()
    assert len(state["participants"]) == 1
    assert state["participants"][0]["total_minutes"] == 0
    assert state["participants"][0]["last_synced_at"] is None


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


def test_competition_state_filters_totals_to_competition_date_range() -> None:
    conn = connect(":memory:")
    app = create_app(
        Settings(db_path=":memory:", admin_token=ADMIN_TOKEN),
        conn=conn,
    )
    api = TestClient(app)
    create_competition(api)
    participant = create_participant(api)

    response = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json={
            "device": {"name": "Participant iPhone", "app_version": "1.0.0", "ios_version": "18.0"},
            "range": {"start_date": "2026-01-31", "end_date": "2026-03-01"},
            "timezone_identifier": "America/New_York",
            "days": [
                {"date": "2026-01-31", "exercise_minutes": 100},
                {"date": "2026-02-01", "exercise_minutes": 20},
                {"date": "2026-02-02", "exercise_minutes": 30},
                {"date": "2026-03-01", "exercise_minutes": 200},
            ],
        },
    )
    assert response.status_code == 200

    state = api.get("/api/v1/competition?as_of_date=2026-02-28").json()

    assert state["as_of_date"] == "2026-02-28"
    assert state["effective_actual_end_date"] == "2026-02-28"
    assert state["participants"][0]["total_minutes"] == 50
    assert state["participants"][0]["days_synced"] == 2
    assert state["daily_series"] == {
        participant["id"]: [
            {"date": "2026-02-01", "exercise_minutes": 20},
            {"date": "2026-02-02", "exercise_minutes": 30},
        ]
    }


def test_default_competition_state_supports_more_than_two_participants() -> None:
    api = client()
    empty = api.get("/api/v1/competition").json()
    assert empty["participants"] == []

    participants = []
    for index in range(8):
        participant = create_participant(api, f"Runner {index + 1}")
        participants.append(participant)
        response = api.post(
            "/api/v1/sync/exercise-days",
            headers={"Authorization": f"Bearer {participant['sync_token']}"},
            json=sync_payload(minutes=(index + 1) * 10),
        )
        assert response.status_code == 200
        if index in {0, 3, 7}:
            state = api.get("/api/v1/competition").json()
            assert len(state["participants"]) == index + 1
            assert [item["rank"] for item in state["participants"]] == list(range(1, index + 2))

    final_state = api.get("/api/v1/competition").json()
    assert final_state["leader"]["id"] == participants[-1]["id"]
    assert final_state["margin"] == 10


def test_competition_state_accepts_naive_sqlite_sync_timestamps() -> None:
    api = client()
    participant = create_participant(api, "Runner")
    api.app.state.store.conn.execute(
        "UPDATE participants SET last_synced_at = datetime('now') WHERE id = ?",
        (participant["id"],),
    )
    api.app.state.store.conn.commit()

    response = api.get("/api/v1/competition")

    assert response.status_code == 200
    assert response.json()["participants"][0]["id"] == participant["id"]


def test_competition_api_archiving_default_switching_and_fallback() -> None:
    api = client()
    default_id = api.get("/api/v1/competition?as_of_date=2026-12-31").json()["competition"]["id"]

    monthly = create_competition(api)
    assert monthly["participant_count"] == 0
    assert monthly["is_default"] is False

    duplicate = api.post(
        "/api/v1/admin/competitions",
        headers=admin_headers(),
        json={
            "name": "Duplicate February",
            "slug": "february-minutes",
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
        },
    )
    assert duplicate.status_code == 409

    invalid_dates = api.post(
        "/api/v1/admin/competitions",
        headers=admin_headers(),
        json={
            "name": "Invalid Dates",
            "slug": "invalid-dates",
            "start_date": "2026-03-01",
            "end_date": "2026-02-01",
        },
    )
    assert invalid_dates.status_code == 422

    by_slug = api.get("/api/v1/competitions/by-slug/february-minutes/state?as_of_date=2026-02-28")
    assert by_slug.status_code == 200
    assert by_slug.json()["competition"]["id"] == monthly["id"]

    archived = api.post(
        f"/api/v1/admin/competitions/{monthly['id']}/archive",
        headers=admin_headers(),
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    public_ids = {item["id"] for item in api.get("/api/v1/competitions").json()}
    assert monthly["id"] not in public_ids

    restored = api.post(
        f"/api/v1/admin/competitions/{monthly['id']}/restore",
        headers=admin_headers(),
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"

    selected = api.post(
        f"/api/v1/admin/competitions/{monthly['id']}/default",
        headers=admin_headers(),
    )
    assert selected.status_code == 200
    assert selected.json()["is_default"] is True
    state = api.get("/api/v1/competition?as_of_date=2026-02-28").json()
    assert state["competition"]["id"] == monthly["id"]

    api.app.state.store.conn.execute(
        "UPDATE settings SET value = ? WHERE key = ?",
        ("missing-competition", "default_competition_id"),
    )
    api.app.state.store.conn.commit()
    fallback = api.get("/api/v1/competition?as_of_date=2026-12-31")
    assert fallback.status_code == 200
    assert fallback.json()["competition"]["id"] == default_id


def test_competition_memberships_reuse_health_data_with_overrides_and_removal() -> None:
    api = client()
    participant = create_participant(api, "Runner")
    monthly = create_competition(api)

    membership = api.post(
        f"/api/v1/admin/competitions/{monthly['id']}/participants",
        headers=admin_headers(),
        json={
            "participant_id": participant["id"],
            "display_name_override": "February Runner",
            "color_override": "#ff00ff",
        },
    )
    assert membership.status_code == 201
    assert membership.json()["display_name"] == "February Runner"
    assert membership.json()["color"] == "#ff00ff"
    assert membership.json()["sync_token"] is None

    response = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json={
            "device": {"name": "Participant iPhone", "app_version": "1.0.0", "ios_version": "18.0"},
            "range": {"start_date": "2026-01-01", "end_date": "2026-03-01"},
            "timezone_identifier": "America/New_York",
            "days": [
                {"date": "2026-01-01", "exercise_minutes": 40},
                {"date": "2026-02-01", "exercise_minutes": 20},
                {"date": "2026-02-02", "exercise_minutes": 30},
                {"date": "2026-03-01", "exercise_minutes": 200},
            ],
        },
    )
    assert response.status_code == 200

    default_state = api.get("/api/v1/competition?as_of_date=2026-12-31").json()
    assert default_state["participants"][0]["total_minutes"] == 290

    monthly_state = api.get(f"/api/v1/competitions/{monthly['id']}/state?as_of_date=2026-02-28").json()
    assert monthly_state["participants"][0]["display_name"] == "February Runner"
    assert monthly_state["participants"][0]["color"] == "#ff00ff"
    assert monthly_state["participants"][0]["total_minutes"] == 50

    hidden = api.patch(
        f"/api/v1/admin/competitions/{monthly['id']}/participants/{participant['id']}",
        headers=admin_headers(),
        json={"active": False},
    )
    assert hidden.status_code == 200
    assert hidden.json()["active"] is False
    inactive_state = api.get(f"/api/v1/competitions/{monthly['id']}/state?as_of_date=2026-02-28").json()
    assert inactive_state["participants"] == []

    removed = api.delete(
        f"/api/v1/admin/competitions/{monthly['id']}/participants/{participant['id']}",
        headers=admin_headers(),
    )
    assert removed.status_code == 200
    assert removed.json()["deleted"] is True
    preserved = api.get("/api/v1/competition?as_of_date=2026-12-31").json()
    assert preserved["participants"][0]["total_minutes"] == 290


def test_admin_can_create_participant_inside_one_competition() -> None:
    api = client()
    monthly = create_competition(api)

    membership = api.post(
        f"/api/v1/admin/competitions/{monthly['id']}/participants",
        headers=admin_headers(),
        json={"display_name": "Monthly Runner", "color": "#3366ff"},
    )

    assert membership.status_code == 201
    body = membership.json()
    assert body["display_name"] == "Monthly Runner"
    assert body["sync_token"]

    default_state = api.get("/api/v1/competition?as_of_date=2026-02-28").json()
    assert default_state["participants"] == []

    monthly_state = api.get(f"/api/v1/competitions/{monthly['id']}/state?as_of_date=2026-02-28").json()
    assert [participant["id"] for participant in monthly_state["participants"]] == [body["participant_id"]]


def test_sync_me_and_sync_response_include_active_competition_memberships() -> None:
    api = client()
    participant = create_participant(api, "Runner")
    monthly = create_competition(api)
    archived = create_competition(
        api,
        name="Archived Minutes",
        slug="archived-minutes",
        start_date="2026-04-01",
        end_date="2026-04-30",
    )

    for competition in [monthly, archived]:
        added = api.post(
            f"/api/v1/admin/competitions/{competition['id']}/participants",
            headers=admin_headers(),
            json={"participant_id": participant["id"]},
        )
        assert added.status_code == 201
    archive = api.post(f"/api/v1/admin/competitions/{archived['id']}/archive", headers=admin_headers())
    assert archive.status_code == 200

    sync = api.post(
        "/api/v1/sync/exercise-days",
        headers={"Authorization": f"Bearer {participant['sync_token']}"},
        json={
            "device": {"name": "Participant iPhone", "app_version": "1.0.0", "ios_version": "18.0"},
            "range": {"start_date": "2026-01-01", "end_date": "2026-02-02"},
            "timezone_identifier": "America/New_York",
            "days": [
                {"date": "2026-01-01", "exercise_minutes": 40},
                {"date": "2026-02-01", "exercise_minutes": 20},
                {"date": "2026-02-02", "exercise_minutes": 30},
            ],
        },
    )
    assert sync.status_code == 200
    sync_competitions = {item["slug"]: item for item in sync.json()["competitions"]}
    assert set(sync_competitions) == {"test-minutes", "february-minutes"}
    assert sync_competitions["test-minutes"]["total_minutes"] == 90
    assert sync_competitions["february-minutes"]["total_minutes"] == 50

    profile = api.get("/api/v1/sync/me", headers={"Authorization": f"Bearer {participant['sync_token']}"})
    assert profile.status_code == 200
    body = profile.json()
    assert body["participant"]["id"] == participant["id"]
    assert {item["slug"] for item in body["competitions"]} == {"test-minutes", "february-minutes"}


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
