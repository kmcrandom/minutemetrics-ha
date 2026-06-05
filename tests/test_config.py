from __future__ import annotations

import json

from minutemetrics.config import load_settings


def test_load_settings_from_home_assistant_options(tmp_path, monkeypatch) -> None:
    options_path = tmp_path / "options.json"
    db_path = tmp_path / "minutemetrics.sqlite"
    options_path.write_text(
        json.dumps(
            {
                "auth": {"admin_token": "ha-admin-token"},
                "competition": {
                    "name": "Family Minutes",
                    "start_date": "2026-01-01",
                    "end_date": "2026-12-31",
                },
                "database": {"path": str(db_path)},
                "network": {"server_url": "https://minutemetrics.example.test"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINUTEMETRICS_OPTIONS_PATH", str(options_path))
    monkeypatch.delenv("MINUTEMETRICS_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("MINUTEMETRICS_DB_PATH", raising=False)
    monkeypatch.delenv("MINUTEMETRICS_COMPETITION_NAME", raising=False)
    monkeypatch.delenv("MINUTEMETRICS_COMPETITION_START_DATE", raising=False)
    monkeypatch.delenv("MINUTEMETRICS_COMPETITION_END_DATE", raising=False)
    monkeypatch.delenv("MINUTEMETRICS_SERVER_URL", raising=False)

    settings = load_settings()

    assert settings.admin_token == "ha-admin-token"
    assert settings.competition_name == "Family Minutes"
    assert settings.competition_start_date == "2026-01-01"
    assert settings.competition_end_date == "2026-12-31"
    assert settings.db_path == str(db_path)
    assert settings.server_url == "https://minutemetrics.example.test"


def test_environment_overrides_home_assistant_options(tmp_path, monkeypatch) -> None:
    options_path = tmp_path / "options.json"
    options_path.write_text(
        json.dumps(
            {
                "auth": {"admin_token": "ha-admin-token"},
                "competition": {"name": "Family Minutes"},
                "database": {"path": str(tmp_path / "options.sqlite")},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINUTEMETRICS_OPTIONS_PATH", str(options_path))
    monkeypatch.setenv("MINUTEMETRICS_ADMIN_TOKEN", "env-admin-token")
    monkeypatch.setenv("MINUTEMETRICS_DB_PATH", str(tmp_path / "env.sqlite"))
    monkeypatch.setenv("MINUTEMETRICS_COMPETITION_NAME", "Env Minutes")
    monkeypatch.setenv("MINUTEMETRICS_SERVER_URL", "https://env.example.test")

    settings = load_settings()

    assert settings.admin_token == "env-admin-token"
    assert settings.competition_name == "Env Minutes"
    assert settings.db_path == str(tmp_path / "env.sqlite")
    assert settings.server_url == "https://env.example.test"
