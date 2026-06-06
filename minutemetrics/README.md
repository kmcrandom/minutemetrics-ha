# MinuteMetrics Home Assistant App

MinuteMetrics receives Apple Health Exercise Minutes from paired iOS devices, stores daily totals, and serves the competition dashboard and API.

## Features

- Participant-based sync using per-participant bearer tokens.
- Persistent SQLite storage under `/data`.
- Home Assistant ingress dashboard.
- Multiple admin-managed competitions with independent date ranges.
- Optional Home Assistant user or `person` entity links for participants.
- Admin dashboard and API for competition management, participant management, token rotation, and sensor payloads.

## Installation

Published installs use the pre-built GHCR image declared in `config.yaml`:

1. Add this repository URL to Home Assistant.
2. Go to Settings -> Apps -> Install App.
3. Install MinuteMetrics.
4. Open the Configuration tab.
5. Change `auth.admin_token` from `change-me-before-use` to a long private value.
6. Start the app.
7. Open the Admin page and create your first competition.

The SQLite database is stored at `/data/minutemetrics.sqlite` by default and persists across app restarts and upgrades.

## Configuration

Example app options:

```yaml
auth:
  admin_token: "replace-with-a-long-random-token"
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

`network.server_url` is embedded in iOS pairing QR codes. Use a URL the iPhone can reach from the networks where sync should work.

## Local Development

Run locally from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
MINUTEMETRICS_ADMIN_TOKEN=replace-with-local-admin-token .venv/bin/python -m minutemetrics
```

The API will listen on `http://0.0.0.0:8080` by default.

For local Home Assistant testing before a container image has been published, copy this `minutemetrics` directory to the Home Assistant local apps directory and temporarily remove the `image` field from the copied `config.yaml` so Supervisor builds the local Dockerfile.

## Create a Competition and Participant

Open the MinuteMetrics Admin page in Home Assistant:

1. Enter the configured admin token.
2. Create a competition with a name, slug, start date, and end date.
3. Add a participant to the competition.
4. Scan the displayed QR code with the MinuteMetrics iOS app.

The QR code contains the configured server URL and the participant sync token. The sync token is shown only at pairing time and should be treated as a private credential.

For the iOS app server URL, use the Home Assistant host and exposed app port.

```text
http://HOME_ASSISTANT_IP:8080
```

The dashboard is available at:

```text
http://HOME_ASSISTANT_IP:8080/
```

## HTTPS Sync

For remote iPhone sync, use an HTTPS reverse proxy in front of the exposed MinuteMetrics app port:

```text
https://minutemetrics.example.com  ->  http://HOME_ASSISTANT_IP:8080
```

The iOS app should use the HTTPS URL. TLS terminates at the reverse proxy on port 443, and the proxy forwards traffic to the Home Assistant app on port 8080 inside the trusted network.

Avoid using the Home Assistant ingress URL for iOS sync. Ingress is designed for browser access through Home Assistant and may require Home Assistant session cookies that the iOS background sync process will not have.

## Identity Model

MinuteMetrics participants are the stable identity for competition history. A participant can optionally link to a Home Assistant user ID or `person` entity ID, but those links can be changed or cleared without deleting exercise-minute data.

## Security

- Change the default admin token before using the app on a network.
- Treat participant sync tokens as private credentials.
- Do not publish live Home Assistant options files or SQLite databases.
