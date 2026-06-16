# MinuteMetrics Home Assistant App

MinuteMetrics receives Apple Health Exercise Minutes from paired iOS devices, stores daily totals, and serves a Home Assistant competition dashboard.

This repository contains the Home Assistant app, backend API, dashboard assets, packaging, and backend tests. The companion iOS app lives in a separate repository.

## Status

MinuteMetrics is pre-release software. The API, dashboard, and Home Assistant app packaging are under active development.

## Repository Layout

```text
minutemetrics/          Home Assistant app, backend API, dashboard assets
specs/                  Product, API, dashboard, app, and packaging specs
tests/                  Backend API and configuration tests
.github/workflows/      CI and Home Assistant image publishing workflows
```

## Specification Set

- [Product Requirements](specs/product-requirements.md)
- [System Architecture](specs/system-architecture.md)
- [Home Assistant App Spec](specs/home-assistant-app.md)
- [API and Data Model Spec](specs/api-data-model.md)
- [Dashboard Spec](specs/dashboard.md)
- [Multi-Competition Dashboard Change Spec](specs/change-multi-competition-dashboard.md)
- [Multi-Competition Dashboard Implementation Plan](specs/plan-multi-competition-dashboard.md)
- [Packaging and Distribution Spec](specs/packaging-distribution.md)
- [Verification Plan](specs/verification.md)
- [Implementation Roadmap](specs/implementation-roadmap.md)

## Development

Run tests:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
```

Run the backend locally:

```bash
MINUTEMETRICS_ADMIN_TOKEN=replace-with-local-admin-token .venv/bin/python -m minutemetrics
```

`MINUTEMETRICS_ADMIN_TOKEN` must be a non-placeholder value of at least 32 characters. The backend refuses to start with the shipped Home Assistant placeholder token or a short admin token.

## Home Assistant App

The Home Assistant app source lives in [minutemetrics](minutemetrics). See [minutemetrics/README.md](minutemetrics/README.md) for installation and configuration details.

Participants are created from the Home Assistant dashboard. The dashboard displays a pairing QR code for the companion iOS app after creating a participant.

## Distribution

MinuteMetrics is structured as a Home Assistant app repository with a pre-built GHCR container image. The initial published image target is `aarch64` for Home Assistant Yellow-class devices. Additional architectures can be added after they are tested.

For remote sync, place an HTTPS reverse proxy in front of the exposed MinuteMetrics app port and set `network.server_url` to that public URL.

## Security Notes

Do not commit live Home Assistant option files, SQLite databases, participant sync tokens, admin tokens, local IP addresses, or local filesystem paths.

The shipped Home Assistant app placeholder admin token is not accepted at runtime. Configure a long private `auth.admin_token` of at least 32 characters before starting the app.
