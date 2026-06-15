from __future__ import annotations

import json

import pytest

from minutemetrics.config import load_settings


def test_load_settings_from_home_assistant_options(tmp_path, monkeypatch) -> None:
    options_path = tmp_path / "options.json"
    db_path = tmp_path / "minutemetrics.sqlite"
    options_path.write_text(
        json.dumps(
            {
                "auth": {"admin_token": "ha-admin-token", "dashboard_token": "ha-dashboard-token"},
                "database": {"path": str(db_path)},
                "network": {"server_url": "https://minutemetrics.example.test"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINUTEMETRICS_OPTIONS_PATH", str(options_path))
    monkeypatch.delenv("MINUTEMETRICS_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("MINUTEMETRICS_DASHBOARD_TOKEN", raising=False)
    monkeypatch.delenv("MINUTEMETRICS_DB_PATH", raising=False)
    monkeypatch.delenv("MINUTEMETRICS_SERVER_URL", raising=False)

    settings = load_settings()

    assert settings.admin_token == "ha-admin-token"
    assert settings.dashboard_token == "ha-dashboard-token"
    assert settings.db_path == str(db_path)
    assert settings.server_url == "https://minutemetrics.example.test"


def test_environment_overrides_home_assistant_options(tmp_path, monkeypatch) -> None:
    options_path = tmp_path / "options.json"
    options_path.write_text(
        json.dumps(
            {
                "auth": {"admin_token": "ha-admin-token", "dashboard_token": "ha-dashboard-token"},
                "database": {"path": str(tmp_path / "options.sqlite")},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINUTEMETRICS_OPTIONS_PATH", str(options_path))
    monkeypatch.setenv("MINUTEMETRICS_ADMIN_TOKEN", "env-admin-token")
    monkeypatch.setenv("MINUTEMETRICS_DASHBOARD_TOKEN", "env-dashboard-token")
    monkeypatch.setenv("MINUTEMETRICS_DB_PATH", str(tmp_path / "env.sqlite"))
    monkeypatch.setenv("MINUTEMETRICS_SERVER_URL", "https://env.example.test")

    settings = load_settings()

    assert settings.admin_token == "env-admin-token"
    assert settings.dashboard_token == "env-dashboard-token"
    assert settings.db_path == str(tmp_path / "env.sqlite")
    assert settings.server_url == "https://env.example.test"


def test_placeholder_admin_token_is_rejected(tmp_path, monkeypatch) -> None:
    options_path = tmp_path / "options.json"
    options_path.write_text(
        json.dumps({"auth": {"admin_token": "change-me-before-use"}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINUTEMETRICS_OPTIONS_PATH", str(options_path))
    monkeypatch.delenv("MINUTEMETRICS_ADMIN_TOKEN", raising=False)

    with pytest.raises(ValueError, match="auth.admin_token"):
        load_settings()


def test_missing_admin_token_is_rejected(tmp_path, monkeypatch) -> None:
    options_path = tmp_path / "options.json"
    options_path.write_text(json.dumps({}), encoding="utf-8")

    monkeypatch.setenv("MINUTEMETRICS_OPTIONS_PATH", str(options_path))
    monkeypatch.delenv("MINUTEMETRICS_ADMIN_TOKEN", raising=False)

    with pytest.raises(ValueError, match="auth.admin_token"):
        load_settings()


def test_placeholder_environment_admin_token_is_rejected(tmp_path, monkeypatch) -> None:
    options_path = tmp_path / "options.json"
    options_path.write_text(
        json.dumps({"auth": {"admin_token": "ha-admin-token"}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINUTEMETRICS_OPTIONS_PATH", str(options_path))
    monkeypatch.setenv("MINUTEMETRICS_ADMIN_TOKEN", "change-me-before-use")

    with pytest.raises(ValueError, match="auth.admin_token"):
        load_settings()
