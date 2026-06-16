from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLACEHOLDER_ADMIN_TOKEN = "change-me-before-use"
MIN_ADMIN_TOKEN_LENGTH = 32


@dataclass(frozen=True)
class Settings:
    db_path: str
    admin_token: str
    dashboard_token: str | None = None
    server_url: str | None = None

    def __post_init__(self) -> None:
        admin_token = _normalize_admin_token(self.admin_token)
        if _is_invalid_admin_token(admin_token):
            raise ValueError(
                f"auth.admin_token must be set to a non-placeholder value of at least {MIN_ADMIN_TOKEN_LENGTH} characters"
            )
        object.__setattr__(self, "admin_token", admin_token)


def load_settings() -> Settings:
    options = _load_app_options()
    auth = options.get("auth", {})
    database = options.get("database", {})
    network = options.get("network", {})

    return Settings(
        db_path=os.environ.get(
            "MINUTEMETRICS_DB_PATH",
            database.get("path") or _default_db_path(),
        ),
        admin_token=os.environ.get(
            "MINUTEMETRICS_ADMIN_TOKEN",
            auth.get("admin_token") or PLACEHOLDER_ADMIN_TOKEN,
        ),
        dashboard_token=_optional_string(os.environ.get("MINUTEMETRICS_DASHBOARD_TOKEN", auth.get("dashboard_token"))),
        server_url=_optional_string(os.environ.get("MINUTEMETRICS_SERVER_URL", network.get("server_url"))),
    )


def _load_app_options() -> dict[str, Any]:
    options_path = Path(os.environ.get("MINUTEMETRICS_OPTIONS_PATH", "/data/options.json"))
    if not options_path.exists():
        return {}
    with options_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def _default_db_path() -> str:
    data_dir = Path("/data")
    if data_dir.exists():
        return str(data_dir / "minutemetrics.sqlite")
    return str(Path.cwd() / "minutemetrics.sqlite")


def _optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_admin_token(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def _is_invalid_admin_token(value: str) -> bool:
    return not value or value == PLACEHOLDER_ADMIN_TOKEN or len(value) < MIN_ADMIN_TOKEN_LENGTH
