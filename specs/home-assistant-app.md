# Home Assistant App Spec

## Purpose

The Home Assistant app stores participant Exercise Minutes, exposes an API for the iOS app, publishes Home Assistant entities, and serves the dashboard.

## Requirements

- Installable as a Home Assistant local app and later as a repository app.
- Configurable without code changes.
- Persistent SQLite storage under `/data`.
- Admin UI for participant management, with API support for automation.
- Token-based participant authentication.
- Dashboard served from the app.
- Optional Home Assistant sensor publishing.
- Public installs use a pre-built GHCR image rather than building on the Home Assistant device.
- Participants can be created from the Home Assistant app UI without command-line access.
- Participant creation shows a QR code containing the configured server URL and generated sync token.

## App Configuration

Example:

```yaml
auth:
  admin_token: "replace-with-a-long-random-token"
competition:
  name: "Exercise Minutes"
  start_date: "2026-01-01"
  end_date: "2026-12-31"
database:
  path: "/data/minutemetrics.sqlite"
dashboard:
  theme: "system"
home_assistant:
  publish_entities: true
  publish_method: "rest"
network:
  server_url: "https://minutemetrics.example.com"
```

Participants should be created through the dashboard admin view or API, not hardcoded in YAML.

The `network.server_url` option is the URL embedded in iOS setup QR codes. It should be the externally reachable MinuteMetrics API origin, such as a reverse-proxied HTTPS URL.

Participants can optionally be linked to Home Assistant users or `person` entities. The link is metadata only; the app must continue to work for participants with no Home Assistant account.

## Runtime

Current stack:

- Python FastAPI for the API.
- SQLite for storage.
- Static frontend assets served by the same service.
- Home Assistant base image selected with `BUILD_ARCH` during image builds.
- Python installed in the Dockerfile with Alpine packages.
- `run.sh` exports `PYTHONPATH=/app/src` and launches `python3 -m minutemetrics`.

The app must not use `build.yaml`. Published installs use the `image` field in `config.yaml` and pull `ghcr.io/kmcrandom/minutemetrics-ha:<version>`. The initial supported architecture is `aarch64` for Home Assistant Yellow. Future `amd64` support requires a tested published image before adding the architecture to `config.yaml`.

Local development builds remain possible by removing the `image` field from a copied local app config and letting Supervisor build the Dockerfile.

The app reads Home Assistant options from `/data/options.json`. Environment variables remain supported for local Mac development and override app options.

## Home Assistant Integration

Initial implementation:

- Publish sensors through Home Assistant REST API using the supervisor-provided environment/context when available.
- Allow admins to record optional Home Assistant user IDs or `person` entity IDs on participant records.

Future implementation:

- MQTT discovery.
- Native custom integration.
- Assisted lookup of Home Assistant users/persons from the admin UI when supported by the runtime permissions.

## App Endpoints

The app should implement the API in [API and Data Model Spec](api-data-model.md).

Additional local endpoints:

- `GET /` dashboard app.
- `GET /api/v1/app-config` non-secret UI configuration.
- `POST /api/v1/admin/pairing-qr` pairing QR code generation for a newly created token.

## Admin Features

- Create participant.
- Show pairing QR code after participant creation.
- Edit participant display name.
- Pick participant color.
- Link, change, or clear optional Home Assistant user/person association.
- Rotate participant token.
- Deactivate participant.
- Generate iOS setup link.
- See last sync status.

Pairing QR payload:

- Use `minutemetrics://pair?server_url=<encoded-url>&sync_token=<encoded-token>`.
- The sync token is only available immediately after participant creation or token rotation.
- The UI must treat the sync token as a secret and should not show it after the pairing moment unless explicitly rotated.

## Implementation Plan

1. Create app metadata: `config.yaml`, `Dockerfile`, `run.sh`, and repository metadata.
2. Create FastAPI service.
3. Add SQLite schema and migrations.
4. Add configuration loading from Home Assistant app options.
5. Implement participant admin endpoints.
6. Implement sync endpoint.
7. Implement aggregate competition endpoint.
8. Implement optional Home Assistant user/person link fields.
9. Implement Home Assistant entity publisher.
10. Serve dashboard static assets.
11. Add app documentation and install instructions.
12. Add integration tests for API and database behavior.
13. Publish a pre-built `aarch64` image through GitHub Actions.
14. Add dashboard participant creation and QR pairing flow.

## Acceptance Criteria

- App starts from a clean install.
- Data persists across app restarts.
- Admin can create participants and generate setup links.
- Admin can create participants from the dashboard without using curl.
- Admin receives a QR code that can configure the iOS app with server URL and sync token.
- Admin can optionally link a participant to a Home Assistant user/person and later clear that link.
- iOS app can sync with participant token.
- Dashboard loads from Home Assistant.
- HA sensors update after sync when publishing is enabled.
- Home Assistant Yellow can install by pulling the pre-built image without compiling dependencies locally.
