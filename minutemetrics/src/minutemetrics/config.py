from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    db_path: str
    admin_token: str
    server_url: str | None = None


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
            auth.get("admin_token") or "change-me-before-use",
        ),
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
