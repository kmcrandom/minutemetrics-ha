# MinuteMetrics Changelog

## 0.2.4

- Fixed a flaky default competition fallback test in CI.
- Renamed Admin competition membership fields to participant name and participant color.
- Removed the Admin pairing server URL field and now require `network.server_url` from app configuration for pairing QR codes.
- Updated Admin participant color presets.

## 0.2.3

- Removed competition setup from Home Assistant app configuration.
- Kept fresh installs stable when no competitions exist yet.
- Added dashboard empty state guidance for creating the first competition from Admin.
- Kept participant sync and Home Assistant sensor payloads from failing before a competition is created.

## 0.2.2

- Added versioned dashboard asset URLs to prevent stale Home Assistant webview JavaScript.
- Fixed first-load fallback when the dashboard has an outdated selected competition ID.

## 0.2.1

- Added dashboard tap popups for iOS and touch devices.
- Added participant color presets while preserving custom color selection.
- Improved Daily Movers heatmap contrast by capping color intensity scaling.
- Renamed Daily Winners to Daily Movers.
- Disabled dashboard/static asset caching so Home Assistant shows updated UI files sooner.

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
