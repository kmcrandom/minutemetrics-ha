# SDD Plan: Multi-Participant Dashboards and Multiple Competitions

## Source Spec

This plan implements [SDD Change Spec: Multi-Participant Dashboards and Multiple Competitions](change-multi-competition-dashboard.md).

## Planning Principles

- Preserve existing installs before adding new UX.
- Ship backend compatibility first, then dashboard and admin features.
- Keep each phase vertically testable.
- Avoid requiring iOS changes before the Home Assistant app can migrate safely.
- Keep `/api/v1/competition` and existing participant sync behavior working throughout the transition.
- Do not publish a release until migrations have been tested against the current `0.1.1` schema.

## Release Strategy

### Release A: Backend Compatibility Foundation

Purpose:

- Make the database and API ready for multiple competitions while preserving the current one-competition user experience.

Contents:

- SQLite migration framework.
- Competition `slug` and `status`.
- `settings.default_competition_id`.
- `competition_memberships`.
- Migration of all existing participants into the default competition.
- Date-range-constrained aggregate calculations.
- Compatibility behavior for `/api/v1/competition`.

Exit gate:

- A `0.1.1` database migrates without losing participants, exercise days, or sync tokens.
- Existing dashboard and iOS sync still work.
- Backend tests cover zero, one, two, four, and eight participants in the default competition.

### Release B: Multiple Competition API And Admin

Purpose:

- Let admins create and manage competitions and memberships.

Contents:

- Competition CRUD/archive/restore endpoints.
- Membership endpoints.
- Admin UI competition list and edit forms.
- Add existing participant to competition.
- Create participant inside a competition.
- Default competition selector.
- Competition-context pairing QR generation.

Exit gate:

- Admin can create overlapping monthly and yearly competitions.
- Admin can add the same participant to both competitions.
- Admin can create a competition with a different participant set.
- Dashboard compatibility endpoint still shows the default competition.

### Release C: Multi-Participant Dashboard

Purpose:

- Remove top-two-only analytics limitations from the dashboard.

Contents:

- Competition switcher.
- Selected competition URL state.
- Multi-participant projection chart.
- Projection mode segmented control.
- Multi-participant Last 14 Days grouped chart.
- Daily Winners across all active participants.
- Participant visibility toggles for larger competitions.

Exit gate:

- Dashboard is visually verified at desktop and mobile widths with 0, 1, 2, 4, and 8 participants.
- Charts remain readable with eight participants.
- Daily Winners considers every active competition member by default.

### Release D: iOS Multi-Competition Sync

Purpose:

- Let one phone join multiple competitions and sync them efficiently.

Contents:

- Server profiles.
- Keychain token storage.
- Joined competition storage.
- `/api/v1/sync/me` discovery.
- Existing QR format compatibility.
- QR parsing with optional competition context.
- Coalesced HealthKit date ranges.
- Multi-profile background sync.

Exit gate:

- One iPhone can pair once with a server and discover multiple joined competitions.
- One iPhone can sync overlapping monthly/yearly competitions with one HealthKit read range.
- Re-pairing after token rotation updates the existing profile.

### Release E: Home Assistant Entity Expansion

Purpose:

- Publish competition-specific Home Assistant sensors.

Contents:

- Competition-specific participant total/today sensors.
- Competition-specific leader and margin sensors.
- Legacy default competition sensors retained.
- Documentation for new entity IDs.

Exit gate:

- Existing automations using default sensors continue to work.
- Competition-specific sensors include competition metadata attributes.

## Detailed Work Plan

### Phase 1: Migration Infrastructure

Tasks:

1. Add `schema_migrations` to [db.py](/Users/kevin/Programming/minutemetrics-ha/minutemetrics/src/minutemetrics/db.py).
2. Replace single `SCHEMA` bootstrap-only behavior with ordered migrations.
3. Add a test helper that creates a database using the current `0.1.1` schema.
4. Add tests proving migrations are idempotent.
5. Add tests proving existing participants, tokens, competitions, exercise days, and sync events survive migration.

Tests:

```bash
.venv/bin/python -m pytest -q tests/test_migrations.py
```

Definition of done:

- A clean database initializes.
- A synthetic `0.1.1` database migrates.
- Running initialization twice does not duplicate memberships or damage data.

### Phase 2: Competition And Membership Schema

Tasks:

1. Add `slug` and `status` columns to `competitions`.
2. Add unique slug index.
3. Add `settings.default_competition_id`.
4. Add `competition_memberships`.
5. Backfill all existing participants into `default`.
6. Update `ensure_default_competition` so HA config creates the initial competition only when none exists.
7. Add store helpers for default competition lookup and active competition lookup.

Tests:

```bash
.venv/bin/python -m pytest -q tests/test_config.py tests/test_api.py tests/test_migrations.py
```

Definition of done:

- Existing `competition.*` HA options no longer overwrite admin-edited competitions after migration.
- Every existing participant becomes an active member of the default competition.

### Phase 3: Date-Range-Correct Aggregation

Tasks:

1. Refactor `competition_state` to accept `competition_id` and `as_of_date`.
2. Filter participants through active memberships.
3. Apply membership display name/color overrides.
4. Filter totals by `start_date <= date <= effective_actual_end_date`.
5. Filter `daily_series` by competition participants and date range.
6. Add `as_of_date` and `effective_actual_end_date` to response metadata.
7. Add `elapsed_day_average_minutes`.
8. Keep `average_daily_minutes` as the existing synced-day average for compatibility.
9. Keep `/api/v1/competition` mapped to the default competition.

Tests:

```bash
.venv/bin/python -m pytest -q tests/test_api.py
```

Definition of done:

- Totals differ correctly between monthly and yearly competitions using the same stored exercise days.
- A participant outside a competition membership does not appear in that competition state.
- Existing `/api/v1/competition` still works.

### Phase 4: Competition API

Tasks:

1. Add admin competition list/create/detail/update endpoints.
2. Add archive and restore endpoints.
3. Add public competition summary list endpoint.
4. Add public competition state endpoints by ID and slug.
5. Validate slugs.
6. Validate date ranges.
7. Add default competition fallback behavior.

Tests:

```bash
.venv/bin/python -m pytest -q tests/test_api.py
```

Definition of done:

- Admin can create two active competitions with overlapping dates.
- Public state can be fetched by ID and slug.
- Archived competitions do not appear in public competition summaries.

### Phase 5: Membership API

Tasks:

1. Add admin membership list endpoint.
2. Add existing-participant membership create endpoint.
3. Add create-participant-and-add-to-competition behavior.
4. Add membership patch endpoint for active flag and display/color overrides.
5. Add membership delete endpoint that removes membership only.
6. Ensure global participant deletion still deletes all memberships and exercise days.

Tests:

```bash
.venv/bin/python -m pytest -q tests/test_api.py
```

Definition of done:

- The same participant can be in two competitions.
- A competition can have a distinct participant set.
- Removing membership does not delete shared Health data.

### Phase 6: Sync Discovery And Response

Tasks:

1. Add `/api/v1/sync/me`.
2. Return authenticated participant profile.
3. Return active memberships and sync date ranges.
4. Update sync response with per-competition summaries.
5. Preserve existing sync request shape.
6. Ensure old iOS clients can still post daily rows.

Tests:

```bash
.venv/bin/python -m pytest -q tests/test_api.py
```

Definition of done:

- Participant token sees only that participant's memberships.
- Sync response includes totals/ranks for each active competition.
- Existing sync tests still pass.

### Phase 7: Admin UI

Tasks:

1. Add competition list to [admin.html](/Users/kevin/Programming/minutemetrics-ha/minutemetrics/src/minutemetrics/static/admin.html).
2. Add competition create/edit/archive/restore controls to [admin.js](/Users/kevin/Programming/minutemetrics-ha/minutemetrics/src/minutemetrics/static/admin.js).
3. Add default competition selector.
4. Add membership management within a selected competition.
5. Add existing participant picker.
6. Add competition-specific display name/color override controls.
7. Add competition-context pairing QR.
8. Keep global participant management available.

Verification:

- Run API tests.
- Run local app.
- Verify admin flows in the browser.
- Check desktop and mobile layouts.

Definition of done:

- Admin can configure monthly and yearly competitions without YAML edits.
- Admin can create a participant directly inside a competition.
- Admin can add an existing participant to another competition.

### Phase 8: Dashboard Competition Switcher

Tasks:

1. Fetch public competition summaries.
2. Add competition selector when more than one active competition exists.
3. Store selected competition in URL query string.
4. Fetch state with `as_of_date=<viewer-local-date>`.
5. Keep `/` useful when only one competition exists.
6. Preserve Home Assistant ingress relative URL behavior.

Verification:

- Browser check with one competition.
- Browser check with two active competitions.
- Browser check after page reload with query string.

Definition of done:

- Dashboard can switch between competitions without admin token.
- Selected competition survives page reload.

### Phase 9: Multi-Participant Charts

Tasks:

1. Replace projection chart top-two selection with visible participant set.
2. Add projection mode segmented control.
3. Add participant visibility toggles when participant count exceeds six.
4. Replace diverging Last 14 Days chart with grouped multi-participant bars.
5. Update Daily Winners to consider all active competition members.
6. Keep all participant cards visible and ranked.
7. Add empty states for zero and one participant.

Verification:

- Browser check with generated data for 0, 1, 2, 4, and 8 participants.
- Desktop viewport.
- Mobile viewport.
- No horizontal overflow.
- No chart label overlap.

Definition of done:

- No chart uses `participants.slice(0, 2)` for core calculations.
- Eight participants remain readable through visibility controls.

### Phase 10: Home Assistant Entities

Tasks:

1. Add competition-specific sensor entity IDs.
2. Include competition metadata attributes.
3. Preserve legacy default competition entity IDs.
4. Update docs and changelog.

Tests:

```bash
.venv/bin/python -m pytest -q tests/test_api.py
```

Definition of done:

- Existing entity IDs remain present for default competition.
- New entity IDs are stable across display name changes where participant IDs are unchanged.

### Phase 11: iOS Implementation

Tasks for the iOS repo:

1. Replace single stored connection with server profile storage.
2. Store sync tokens in Keychain.
3. Add joined competition storage.
4. Update QR parser for optional `competition_id` and `competition_slug`.
5. Add `/api/v1/sync/me` client.
6. Merge duplicate profiles by `server_url` and resolved `participant_id`.
7. Compute coalesced HealthKit date ranges.
8. Sync all enabled server profiles.
9. Display joined competitions and per-competition last sync state.
10. Handle token rotation re-pairing.

Verification:

- Existing QR pairs successfully.
- Competition-context QR pairs successfully.
- Same profile can be re-paired without duplicates.
- One profile can show multiple competitions.
- Overlapping ranges produce one HealthKit read range.
- Disjoint ranges produce multiple coalesced read ranges.

Definition of done:

- One phone can sync one participant into multiple competitions on the same server.

## Suggested PR Breakdown

1. `migrations-competition-memberships`
2. `date-range-competition-state`
3. `competition-admin-api`
4. `membership-admin-api`
5. `sync-me-multi-competition`
6. `admin-competition-ui`
7. `dashboard-competition-switcher`
8. `dashboard-multi-participant-charts`
9. `ha-competition-entities`
10. iOS multi-competition support in the iOS repository

## Risk Register

### Migration Data Loss

Risk:

- Existing SQLite databases are user data.

Mitigation:

- Add migration tests from a captured `0.1.1` schema.
- Keep exercise day rows unchanged.
- Run migrations in transactions.

### Config Overwrite Regression

Risk:

- Current app startup overwrites default competition metadata from HA options.

Mitigation:

- Make HA options bootstrap-only after competitions exist.
- Add explicit test coverage.

### Chart Readability

Risk:

- Multi-participant analytics can become visually noisy.

Mitigation:

- Use visibility toggles.
- Show one projection mode at a time.
- Verify with 8 participants.

### iOS Excessive HealthKit Reads

Risk:

- Multiple competitions could cause duplicate or broad HealthKit reads.

Mitigation:

- Coalesce overlapping ranges.
- Keep disjoint ranges separate.

### Entity Churn

Risk:

- Home Assistant users may build automations around existing entities.

Mitigation:

- Keep legacy default competition entities for at least one release cycle.
- Add competition-specific entities instead of replacing immediately.

## Release Checklist

Before tagging a release that includes any phase:

- Run backend tests.
- Verify migration tests.
- Run local browser smoke tests for affected pages.
- Update [CHANGELOG.md](/Users/kevin/Programming/minutemetrics-ha/minutemetrics/CHANGELOG.md).
- Update relevant specs if behavior changed during implementation.
- Bump `minutemetrics/config.yaml`, `pyproject.toml`, Docker build version, and `minutemetrics.__version__`.
- Push tag and watch the publish workflow.

## Open Planning Questions

- Should Release A and Release B be one release or two?
- Should multi-competition backend ship before the iOS app supports `/sync/me`?
- Should the admin UI support cloning an existing competition to make the next month easier?
- Should public dashboard users be allowed to view archived competitions by direct URL?
