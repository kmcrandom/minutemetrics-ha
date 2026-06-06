# MinuteMetrics Changelog

## 0.2.0

- Added multiple competition support with admin-created competitions.
- Added competition membership management, including adding existing participants to multiple competitions.
- Added per-competition participant display name and color overrides.
- Added a dashboard competition switcher.
- Updated dashboard analytics to support more than two participants.
- Added migration support for existing `0.1.x` installs.
- Added participant sync discovery for joined competitions.

## 0.1.1

- Added a separate admin dashboard at `/admin`.
- Moved participant creation out of the public competition dashboard.
- Added participant editing for names and colors.
- Added participant deletion.
- Added sync-data clearing while preserving participants and pairing tokens.
- Added Home Assistant configuration labels and `YYYY-MM-DD` validation for competition dates.

## 0.1.0

- Initial Home Assistant app release.
- Added Apple Health exercise-minute sync API.
- Added participant pairing with per-participant sync tokens.
- Added Home Assistant ingress dashboard.
- Added persistent SQLite storage.
- Added aarch64 GHCR image publishing.
