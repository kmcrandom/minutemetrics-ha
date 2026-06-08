# Verification Plan

## Accuracy Verification

For each participant:

1. Compare the iOS app local total to Apple Health for the same date range.
2. Sync to the Home Assistant app.
3. Compare the sync response total to the dashboard total.
4. Compare aggregate totals, leader, and margin in the dashboard.

The expected result is exact agreement for the same date range after full resync.

## Unit Tests

Home Assistant app:

- Participant CRUD.
- Optional Home Assistant user/person link, unlink, and relink behavior.
- Token authentication.
- Token rotation.
- Pairing QR generation.
- Exercise day upsert.
- Aggregate totals.
- Leader and margin calculations.
- Stale sync detection.
- Sensor payload generation.
- Archived competition admin constraints:
  - Archived competitions are hidden from the main admin competition table.
  - Archived competitions are reachable from the separate archived view.
  - Archived competitions cannot be edited.
  - Archived competition memberships cannot be added, updated, or removed.
  - Archived competitions can be restored.
  - Archived competitions can be permanently deleted without deleting participants or exercise days.

Dashboard:

- Participant creation form.
- Pairing QR modal.
- Ranking display.
- Empty states.
- More than two participants.
- Stale sync warning.
- Responsive layout.
- Projection labels read "Today's pace", "Weekly pace", and "Average pace".
- Projection popups show the projected end-of-competition total minutes for each pace on hover, tap, and keyboard focus.

Repository and packaging:

- GitHub CI runs backend tests.
- GitHub CI builds the Home Assistant `aarch64` image.
- Published app image tag matches `minutemetrics/config.yaml` version.
- Repository audit finds no committed SQLite databases, local IP addresses, live tokens, or local filesystem paths.

## Integration Tests

- Create competition.
- Archive, restore, and permanently delete an archived competition.
- Create participants.
- Generate pairing QR.
- Link and unlink a participant from a Home Assistant user/person.
- Sync daily payloads for multiple participants.
- Confirm aggregate endpoint.
- Confirm Home Assistant sensor publisher output.
- Confirm resync updates existing days rather than duplicating rows.

## Manual QA

- Fresh Home Assistant app install.
- Home Assistant app restart persistence.
- Participant creation from dashboard.
- QR pairing flow with the companion iOS app.
- Full-year resync from iOS.
- Dashboard on desktop, phone, and Home Assistant panel.
- Reverse-proxied HTTPS sync URL.

## Release Gates

- Historical data remains intact when Home Assistant user/person links change.
- Home Assistant app can recover from restart without data loss.
- Token rotation invalidates previous token.
- Dashboard handles at least four participants.
- Documentation includes privacy and setup-token explanation.
- Home Assistant app installs from the repository using the pre-built image on `aarch64`.
