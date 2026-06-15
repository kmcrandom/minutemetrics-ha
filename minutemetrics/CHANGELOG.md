# MinuteMetrics Changelog

## 0.2.9

- Added copyable server URL and sync token fields to the Admin pairing QR dialog.
- Kept the displayed sync token masked while copying the exact unmasked pairing token.
- Cleared pairing values from the dialog when it closes.

## 0.2.8

- Added a separate Admin archived competitions view.
- Hid archived competitions from the main Admin competition table.
- Kept archived competition details read-only except for restore and permanent delete.
- Allowed permanent deletion of archived non-default competitions while preserving participants and synced exercise data.
- Renamed projection labels to Average pace, Weekly pace, and Today's pace.
- Added projection popups that show each participant's projected end-of-competition total minutes.

## 0.2.7

- Kept the dashboard header actions inline with the competition title on narrow screens.
- Kept the dashboard leader and margin summary on one line on narrow screens.

## 0.2.6

- Added private dashboard data access for Home Assistant ingress, dashboard tokens, admin tokens, and participant-scoped sync tokens.
- Added `auth.dashboard_token` configuration for read-only standalone dashboard access.
- Restructured Admin into overview, competition detail, participant detail, and add-competition pages.
- Hid the Admin access section after unlock and added a clear admin token control.
- Updated dashboard token handling and unauthorized dashboard empty states.
- Updated SDD specs and repo instructions for spec-driven changes.

## 0.2.5

- Added public App Store marketing and support pages.
- Added `/dashboard` as an explicit dashboard route while keeping `/admin` unchanged.
- Served the marketing page at `/` for `minutemetrics.kmcleod.com` without changing the Home Assistant dashboard root.
- Added spacing between the Admin default color label and color presets.

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
