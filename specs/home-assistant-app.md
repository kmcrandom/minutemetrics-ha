# Home Assistant App Spec

## Purpose

The Home Assistant app stores participant Exercise Minutes, exposes an API for the iOS app, publishes Home Assistant entities, and serves the dashboard.

## Requirements

- Installable as a Home Assistant local app and later as a repository app.
- Configurable without code changes.
- Persistent SQLite storage under `/data`.
- Admin UI for competition and participant management, with API support for automation.
- Token-based participant authentication.
- Private dashboard data served from the app.
- Optional Home Assistant sensor publishing.
- Public installs use a pre-built GHCR image rather than building on the Home Assistant device.
- Competitions and participants can be created from the Home Assistant app UI without command-line access.
- Participant creation shows a QR code containing the configured server URL and generated sync token.
- Public App Store support and marketing pages are served by the app without exposing private competition data.

## App Configuration

Example:

```yaml
auth:
  admin_token: "replace-with-a-long-random-token"
  dashboard_token: "replace-with-a-long-random-dashboard-token"
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

Competitions and participants should be created through the dashboard admin view or API, not hardcoded in YAML.

The `network.server_url` option is the URL embedded in iOS setup QR codes. It should be the externally reachable MinuteMetrics API origin, such as a reverse-proxied HTTPS URL.

The `auth.dashboard_token` option grants read-only access to all active dashboard data. It is separate from the admin token and must not authorize admin API endpoints. Home Assistant ingress viewers can also receive full dashboard access through trusted Home Assistant ingress identity, so the dashboard token is primarily for standalone read-only dashboard access outside Home Assistant.

Participants can optionally be linked to Home Assistant users or `person` entities. The link is metadata only; the app must continue to work for participants with no Home Assistant account.

Security hardening:

- The shipped `auth.admin_token` value is a placeholder only and must not be accepted as a live admin credential.
- Runtime startup or admin API initialization must fail closed when `auth.admin_token` is empty, missing, equal to `change-me-before-use`, or shorter than 32 characters after trimming surrounding whitespace.
- Local development may continue to use `MINUTEMETRICS_ADMIN_TOKEN`, but it must also be non-placeholder and at least 32 characters.
- Documentation and tests must make first-run token replacement explicit.

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

- `GET /` dashboard app, except on the public marketing host where it serves the marketing page.
- `GET /dashboard` dashboard app.
- `GET /admin` admin app.
- `GET /support` public support page.
- `GET /api/v1/app-config` non-secret UI configuration.
- `POST /api/v1/admin/pairing-qr` pairing QR code generation for a newly created token.

Dashboard data endpoints require dashboard data access:

- Full access: admin token, dashboard token, or trusted Home Assistant ingress identity.
- Participant access: participant sync token, scoped to active competitions where the participant is an active member.
- No token or untrusted ingress headers: `401 Unauthorized`.

## Admin Features

- Create, edit, archive, restore, and select competitions.
- Show an overview page with a competitions table and an all-participants table.
- Open a competition detail page by clicking a competition row.
- Open a participant detail page by clicking a participant row.
- Add a new competition on a dedicated page.
- Create participant.
- Show pairing QR code after participant creation.
- While the pairing QR code is visible, also show the server URL and sync token fields.
- Provide a copy button for the server URL field and a copy button for the sync token field.
- Mask the displayed sync token like a password, while copying the full unmasked token value.
- Edit participant display name.
- Pick participant color.
- Link, change, or clear optional Home Assistant user/person association.
- Rotate participant token.
- Deactivate participant.
- Generate iOS setup link.
- See last sync status.
- Hide the access form after the admin token is accepted.
- Clear the locally stored admin token from the admin UI.

Pairing QR payload:

- Use `minutemetrics://pair?server_url=<encoded-url>&sync_token=<encoded-token>`.
- The sync token is only available immediately after participant creation or token rotation.
- The UI must treat the sync token as a secret and should not show it after the pairing moment unless explicitly rotated.
- During the pairing moment, the server URL should be readable and copyable, and the sync token should be copyable but visually masked.
- Copy actions should copy the exact values embedded in the QR payload and should provide clear success or failure feedback.

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
- Admin can copy the server URL and the exact sync token while the QR code is displayed.
- The sync token is masked on screen while remaining copyable as the original token.
- Admin can optionally link a participant to a Home Assistant user/person and later clear that link.
- iOS app can sync with participant token.
- Dashboard loads from Home Assistant with full data through trusted ingress identity.
- Unauthenticated public dashboard data requests do not return competition data.
- A participant sync token can load only that participant's assigned competitions.
- A participant sync token cannot see Home Assistant user IDs or person entity IDs in dashboard state responses.
- Oversized participant sync payloads are rejected before SQLite writes.
- The app does not authorize admin routes with the shipped placeholder admin token or short admin tokens.
- HA sensors update after sync when publishing is enabled.
- Home Assistant Yellow can install by pulling the pre-built image without compiling dependencies locally.
