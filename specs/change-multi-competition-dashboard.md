# SDD Change Spec: Multi-Participant Dashboards and Multiple Competitions

## Status

Draft.

## Summary

MinuteMetrics should support more than two participants in dashboard analytics and should support multiple competitions on one Home Assistant app instance. A single person/phone should be able to join multiple competitions without replacing an existing pairing.

This change introduces competition membership as the link between global participant identities and competition-specific scoreboards. Apple Health day rows remain participant/date facts and are aggregated into each competition by date range and membership.

## Problem

MinuteMetrics currently supports more than two participants in the backend, ranking list, admin UI, and sync model, but several dashboard analytics are limited to the top two participants. The product also has one implicit default competition, which prevents common use cases such as monthly and yearly leaderboards running at the same time, or separate competitions for different groups of people.

The iOS pairing model is also single-token oriented in the UI. A person with one phone needs to be able to join multiple competitions on the same server without replacing their existing pairing. The same phone may also sync to more than one MinuteMetrics server.

## Goals

- Support dashboards with more than two participants as a first-class experience.
- Avoid a product-level maximum participant count.
- Define verified dashboard behavior for at least 0, 1, 2, 4, and 8 participants.
- Support multiple competitions on one MinuteMetrics server.
- Allow monthly, yearly, and custom date-range competitions to exist at the same time.
- Allow competitions to have different participant membership.
- Allow the same participant to belong to multiple competitions.
- Preserve existing `0.1.x` installs with a safe migration from the current default competition.
- Keep iOS sync efficient: HealthKit daily data should be read once per needed date range and reused for all joined competitions.

## Non-Goals

- Do not add team competitions in this change.
- Do not add public account registration.
- Do not require Home Assistant user accounts for competition membership.
- Do not require participants to re-pair for the default competition during migration.
- Do not build a native Home Assistant custom integration in this change.
- Do not add viewer authentication in this change.
- Do not add recurring competition templates in the first implementation.

## Current Behavior

- The backend stores one `competitions` row with id `default`.
- The `competitions` table currently has no `slug`, `status`, or explicit default flag.
- Home Assistant `competition.*` options seed and overwrite the default competition on app startup.
- Participants are global records.
- Exercise days are keyed by `(participant_id, date)`.
- Sync tokens resolve to one participant, not one competition membership.
- `GET /api/v1/competition` returns the default competition state.
- Current aggregate totals are not fully constrained by the competition date range; `total_for_participant` and `daily_series` use all submitted exercise days.
- Participant cards render all participants.
- Leader and margin work across all ranked participants.
- Projection chart, Last 14 Days, and Daily Winners use `data.participants.slice(0, 2)`.

## Design Decisions

- Participants are global identities.
- Competitions are scoreboard contexts with date ranges.
- Membership controls which participants appear in each competition.
- Exercise day rows remain global participant/day facts, not competition-specific rows.
- Participant sync tokens remain participant-level credentials.
- One token can sync one participant's data for every competition that participant has joined.
- Existing `/api/v1/competition` remains a default-competition compatibility endpoint.
- Dashboard aggregate endpoints are public, as they are today. Admin mutation endpoints remain token-protected.
- Competition state endpoints accept an optional `as_of_date` so dashboard "today" and projection calculations can be based on the viewer's local date.

## Proposed Concepts

### Competition

A competition defines the scoreboard period and display context.

Fields:

- `id`
- `name`
- `slug`
- `start_date`
- `end_date`
- `status`: `active` or `archived`
- `timezone_policy`
- `created_at`
- `updated_at`

Rules:

- `id` is stable and opaque.
- `slug` is URL-safe, unique, and user-editable with validation.
- Date ranges use `YYYY-MM-DD`.
- Active competitions appear in the dashboard switcher.
- Archived competitions are hidden from default dashboard lists but remain queryable by admin.
- A setting named `default_competition_id` identifies the competition used by `/api/v1/competition` and `/`.

### Participant

A participant remains the stable person identity on the server.

Existing participant fields remain valid:

- `id`
- `display_name`
- `color`
- `token_hash`
- `active`
- Home Assistant user/person links
- sync metadata

### Competition Membership

Membership links participants to competitions.

Fields:

- `competition_id`
- `participant_id`
- `display_name_override`
- `color_override`
- `active`
- `joined_at`
- `created_at`
- `updated_at`

Rules:

- A participant can belong to many competitions.
- A competition can contain many participants.
- Display name and color default to the participant record unless overridden for that competition.
- Removing a participant from a competition removes the membership, not the participant or their Health data.
- Deleting a participant deletes that participant and all of their Health data across all competitions.

## Data Model Changes

### Migration Support

Add explicit SQLite migration tracking before making schema changes.

Preferred table:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
```

Migration rules:

- Migrations must run inside transactions.
- Migrations must be idempotent enough to survive app restart after a failed startup.
- Existing data must not be destroyed.
- Tests must cover migration from the current `0.1.1` schema.

### Competitions Table

The existing `competitions` table must gain:

- `slug TEXT`
- `status TEXT NOT NULL DEFAULT 'active'`

Migration rules:

- Existing row `default` gets slug `default`.
- Existing row `default` gets status `active`.
- A unique index is added for non-null slugs.
- `settings.default_competition_id` is set to `default` if missing.

Suggested index:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_competitions_slug ON competitions(slug);
```

### Competition Memberships Table

Add:

```sql
CREATE TABLE IF NOT EXISTS competition_memberships (
  competition_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  display_name_override TEXT,
  color_override TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  joined_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (competition_id, participant_id),
  FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE CASCADE,
  FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
);
```

Suggested indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_memberships_participant_id
  ON competition_memberships(participant_id);

CREATE INDEX IF NOT EXISTS idx_memberships_competition_active
  ON competition_memberships(competition_id, active);
```

Migration rules:

1. Ensure the existing `default` competition exists.
2. Create `competition_memberships`.
3. Insert one active membership in `default` for each existing participant.
4. Keep existing sync tokens valid.
5. Preserve all `exercise_days` rows unchanged.

### Exercise Days

Keep `exercise_days` keyed by participant and date:

```text
participant_id + date -> exercise_minutes
```

Rationale:

- Apple Health Exercise Minutes are person/day facts, not competition facts.
- Multiple competitions can aggregate the same daily data over different date ranges.
- A yearly and monthly competition should not duplicate identical HealthKit day rows.

Aggregation rule:

- Competition totals, today values, averages, projections, ranks, margins, and daily series must filter by both competition membership and competition date range.
- Competition state calculations use an `as_of_date`.
- If `as_of_date` is omitted, the backend defaults it to the Home Assistant/server local date.
- The dashboard should pass the viewer's local `YYYY-MM-DD` date when fetching competition state.
- The effective actual-data end date is `min(competition.end_date, as_of_date)`.
- If `as_of_date` is before `competition.start_date`, actual totals and daily series should be empty or zero.

Metric definitions:

- `total_minutes`: sum of stored exercise days for active members where `competition.start_date <= date <= effective_actual_end_date`.
- `today_minutes`: sum for `as_of_date` when `as_of_date` falls inside the competition range; otherwise `0`.
- `days_synced`: count of stored day rows for the participant inside the effective competition range.
- `average_daily_minutes`: existing compatibility field; keep current synced-day semantics unless a separate elapsed-day field is added.
- `elapsed_day_average_minutes`: preferred new field for projection pace, calculated as `total_minutes / elapsed_competition_days`.
- `projected_total`: based on elapsed-day average unless the dashboard has selected a different projection mode.

## Home Assistant Configuration Changes

Existing config:

```yaml
competition:
  name: Exercise Minutes
  start_date: ""
  end_date: ""
```

New behavior:

- These options are bootstrap defaults for the initial/default competition.
- After migration to admin-managed competitions, app startup must not overwrite an existing competition's admin-edited name or dates on every restart.
- If no competitions exist, the app creates the default competition from the Home Assistant options.
- If competitions already exist, the admin UI is the source of truth for competition name, slug, status, and dates.
- The config UI should keep these fields for backward compatibility until a later release decides whether to remove or rename them.

## API Changes

### Competition Admin

Add:

```http
GET /api/v1/admin/competitions
POST /api/v1/admin/competitions
GET /api/v1/admin/competitions/{competition_id}
PATCH /api/v1/admin/competitions/{competition_id}
POST /api/v1/admin/competitions/{competition_id}/archive
POST /api/v1/admin/competitions/{competition_id}/restore
```

Optional later endpoint:

```http
DELETE /api/v1/admin/competitions/{competition_id}
```

Delete behavior:

- Initial implementation should archive rather than hard-delete competitions.
- Hard delete is intentionally deferred because exercise day rows are shared across competitions.

### Membership Admin

Add:

```http
GET /api/v1/admin/competitions/{competition_id}/participants
POST /api/v1/admin/competitions/{competition_id}/participants
PATCH /api/v1/admin/competitions/{competition_id}/participants/{participant_id}
DELETE /api/v1/admin/competitions/{competition_id}/participants/{participant_id}
```

`POST` supports:

- Adding an existing participant to a competition.
- Creating a new participant and immediately adding them to the competition.

`DELETE` behavior:

- Removes membership only.
- Does not delete the participant.
- Does not delete `exercise_days`.

### Public Competition State

Keep backwards compatibility:

```http
GET /api/v1/competition
```

Behavior:

- Returns the default active competition.
- If `settings.default_competition_id` is missing or invalid, returns the first active competition by creation date.

Add:

```http
GET /api/v1/competitions
GET /api/v1/competitions/{competition_id}/state?as_of_date=YYYY-MM-DD
GET /api/v1/competitions/by-slug/{slug}/state?as_of_date=YYYY-MM-DD
```

`GET /api/v1/competitions` returns summaries only:

- `id`
- `name`
- `slug`
- `start_date`
- `end_date`
- `status`
- participant count

Competition state response changes:

- Include `competition.id`.
- Include `competition.slug`.
- Include `competition.status`.
- Include `as_of_date`.
- Include `effective_actual_end_date`.
- Include only participants who are active members of the requested competition.
- Use membership display name/color overrides when present.
- Aggregate totals only across the requested competition date range.
- Return `daily_series` only for participants in the requested competition and only for dates in the requested competition date range.

### Participant Sync

Current:

```http
POST /api/v1/sync/exercise-days
```

Keep the endpoint, but update behavior:

- Authenticate participant by token.
- Store submitted day rows globally by participant/date.
- Recalculate affected competition summaries from stored day rows and active memberships.
- Return sync results per active competition.
- Include the list of active memberships in the response so iOS can show joined competitions.

The sync request does not need `competition_id` for normal operation. Optional `competition_ids` may be added later if targeted sync proves useful.

Example response:

```json
{
  "participant_id": "participant-123",
  "accepted_count": 31,
  "changed_count": 2,
  "server_timestamp": "2026-06-06T12:00:00Z",
  "competitions": [
    {
      "competition_id": "year-2026",
      "slug": "year-2026",
      "name": "2026 Exercise Minutes",
      "total_minutes": 1234,
      "rank": 2
    },
    {
      "competition_id": "june-2026",
      "slug": "june-2026",
      "name": "June Challenge",
      "total_minutes": 210,
      "rank": 1
    }
  ]
}
```

Add metadata endpoint for iOS:

```http
GET /api/v1/sync/me
```

Authentication:

- Uses the participant bearer token.

Returns:

- participant profile.
- active competition memberships.
- date ranges that should be synced.
- server timestamp.

Example:

```json
{
  "participant": {
    "id": "participant-123",
    "display_name": "Casey",
    "color": "#2f80ed"
  },
  "competitions": [
    {
      "id": "year-2026",
      "slug": "year-2026",
      "name": "2026 Exercise Minutes",
      "start_date": "2026-01-01",
      "end_date": "2026-12-31",
      "sync_start_date": "2026-01-01",
      "sync_end_date": "2026-12-31"
    }
  ],
  "server_timestamp": "2026-06-06T12:00:00Z"
}
```

## Pairing Model

Current QR:

```text
minutemetrics://pair?server_url=<server_url>&sync_token=<token>
```

Keep compatibility with the current QR format.

Add optional context parameters:

```text
minutemetrics://pair?server_url=<server_url>&sync_token=<token>&competition_id=<competition_id>&competition_slug=<slug>
```

Interpretation:

- If `competition_id` or `competition_slug` is present, iOS highlights that the pairing came from a specific competition.
- The token still belongs to the participant, not only that competition.
- After pairing, iOS calls `/api/v1/sync/me` to discover every active competition for that participant.

Admin UX:

- Pairing from a global participant detail screen pairs the person generally.
- Pairing from a competition membership screen includes competition context.
- Rotating the participant token invalidates that participant's sync across all competitions on that server.

## iOS App Changes

### Data Model

Replace single stored connection with a list of server profiles.

Suggested local entities:

- `ServerProfile`
  - `id`
  - `server_url`
  - `sync_token`
  - `participant_id`
  - `participant_display_name`
  - `last_sync_at`
  - `enabled`
- `JoinedCompetition`
  - `server_profile_id`
  - `competition_id`
  - `competition_slug`
  - `name`
  - `start_date`
  - `end_date`
  - `sync_start_date`
  - `sync_end_date`
  - `status`
  - `last_total_minutes`
  - `last_rank`
  - `last_sync_at`

Rules:

- Store sync tokens in Keychain, not plain user defaults.
- One phone can store many `ServerProfile` records.
- A single `ServerProfile` can contain many joined competitions.
- If the same `server_url` and `participant_id` are paired again, update the existing profile instead of creating a duplicate.
- If `participant_id` is not known at QR parse time, save a provisional profile and resolve it through `/api/v1/sync/me`.
- Token rotation updates the existing profile token after re-pairing.

### Pairing Flow

On QR scan:

1. Parse `server_url`, `sync_token`, and optional competition context.
2. Save or update a provisional server profile.
3. Call `GET /api/v1/sync/me`.
4. Resolve `participant_id`.
5. Merge with an existing profile if the same `server_url` and `participant_id` already exist.
6. Display joined competitions returned by the server.
7. Let the user run a full sync immediately.

### Sync Flow

On manual full sync:

1. For each enabled server profile, call `/api/v1/sync/me`.
2. Compute coalesced active date ranges from the returned competitions.
3. Cap each range at the iPhone's device-local today.
4. Read HealthKit daily Exercise Minutes once per coalesced range.
5. Submit daily rows to `/api/v1/sync/exercise-days`.
6. Update local competition summary cards from the response.

Example:

- Yearly competition: `2026-01-01` to `2026-12-31`.
- Monthly competition: `2026-06-01` to `2026-06-30`.
- On `2026-06-06`, iOS reads `2026-01-01` to `2026-06-06` once.

Disjoint range example:

- January competition: `2026-01-01` to `2026-01-31`.
- June competition: `2026-06-01` to `2026-06-30`.
- iOS should read two coalesced ranges rather than one broad January-to-June range.

### Background Sync

Background sync should:

- Sync all enabled server profiles.
- Call `/sync/me` first so archived or removed competitions stop syncing.
- Skip archived competitions returned by the server.
- Limit HealthKit reads to relevant coalesced date ranges.
- Prefer incremental reads since the last successful sync, with periodic full resync support.
- Surface partial failures per server profile.

### Local UI

Add:

- Server profile list.
- Joined competition list under each server.
- Last sync status per server and per competition.
- Manual full sync per server profile.
- Disable/enable server profile.
- Remove server profile.
- Re-pair/update token flow.

## Dashboard Changes For More Than Two Participants

### Participant Count

- There is no hard participant maximum in the product model.
- The dashboard must be verified for at least 8 participants.
- For larger competitions, charts may default to a manageable visible subset while keeping the full ranked participant list available.

### Competition Switcher

Add a competition selector near the title.

Behavior:

- If one active competition exists, show the title without a selector.
- If multiple active competitions exist, show a select/tabs control.
- Changing competitions fetches `/api/v1/competitions/{competition_id}/state?as_of_date=<viewer-local-date>`.
- The selected competition should be reflected in the URL, for example:

```text
/?competition=year-2026
```

### Scoreboard

Keep participant cards for all active members.

Enhancements:

- Use rank, display name, total, today, average, projected total, and sync status for every participant.
- Default sort remains rank.
- Membership display name/color overrides appear in competition views.

### Projection Chart

Replace the top-two-only projection chart with a multi-participant projection chart.

Rules:

- Show actual cumulative line for every visible participant.
- Show one projection mode at a time for every visible participant:
  - all-data average.
  - last 7 days.
  - today pace.
- Use a segmented control to choose projection mode.
- For more than six participants, show the top six by default and expose participant visibility toggles.
- Do not render three future lines per participant for many participants; it becomes unreadable.

### Last 14 Days

Replace the diverging top-two chart with a grouped multi-participant chart.

Rules:

- Each day row shows one compact bar per visible participant.
- Bars share a common scale across the visible 14-day window.
- Participant colors identify bars, but tooltips and accessible labels include names.
- For more than six participants, show top six by rank by default and expose participant visibility toggles.

### Daily Winners Heatmap

Update winner calculations to consider all active competition participants by default.

Rules:

- Winner is the participant with the highest minutes for that date.
- Ties use neutral color.
- Tooltip lists winner/tie and top participant values.
- If more than one participant ties for first, tooltip lists tied names.
- If the dashboard adds a visibility filter that changes winner calculations, the UI must clearly label the heatmap as filtered.

### Margin

Keep primary margin as first place minus second place.

Add optional secondary context:

- participant count.
- distance from selected participant to leader when a participant is selected.

## Admin UI Changes

Add competition management:

- Create competition.
- Edit competition name, slug, start date, end date, status.
- Choose the default competition.
- Archive and restore competitions.
- Add existing participant to competition.
- Create participant inside a competition.
- Remove participant from competition without deleting Health data.
- Override participant display name/color for a specific competition.
- Show pairing QR for participant.
- Show competition-specific pairing QR with optional competition context.

Keep global participant management:

- Edit global participant identity.
- Rotate participant token.
- Delete participant and all data.
- Clear all sync data globally.

Clarification:

- Because exercise day rows are global participant/day facts, "clear this competition's data only" is not part of this change. To reset a competition without deleting shared Health data, archive it and create a new competition.

## Home Assistant Entities

Current entity names are global:

- `sensor.minutemetrics_participant_<slug>_total`
- `sensor.minutemetrics_participant_<slug>_today`
- `sensor.minutemetrics_leader`
- `sensor.minutemetrics_margin`

For multiple competitions, add competition-specific entity IDs:

- `sensor.minutemetrics_<competition_slug>_<participant_slug>_total`
- `sensor.minutemetrics_<competition_slug>_<participant_slug>_today`
- `sensor.minutemetrics_<competition_slug>_leader`
- `sensor.minutemetrics_<competition_slug>_margin`

Compatibility:

- Keep existing global entity IDs mapped to the default competition for at least one release cycle.
- Mark legacy entities with attributes showing `competition_id` and `competition_slug`.
- Include `competition_name`, `competition_start_date`, and `competition_end_date` attributes on competition-specific sensors.

## Security And Privacy

- Admin endpoints remain protected by the admin token.
- Participant sync tokens remain secrets.
- A participant token exposes that participant's profile and memberships.
- A participant token allows syncing that participant's data across that participant's memberships.
- A participant token must not allow reading other participants' raw day history outside aggregate competition state.
- Pairing QR codes should be treated as secret until scanned.
- iOS stores tokens in Keychain.

## Backward Compatibility

- Existing iOS pairing URLs remain valid.
- Existing participant tokens remain valid.
- Existing default competition remains available at `/api/v1/competition`.
- Existing dashboard URL `/` continues to work.
- Existing data migrates into the default competition membership set.
- Existing Home Assistant entities continue to represent the default competition for at least one release cycle.
- Existing iOS clients that do not call `/sync/me` can continue syncing the default competition through `/api/v1/sync/exercise-days`.

## Testing And Verification

Backend tests:

- Migration from the current `0.1.1` schema.
- Default competition creation on clean install.
- Home Assistant config no longer overwrites existing admin-managed competitions after migration.
- Competition CRUD.
- Membership CRUD.
- Same participant in multiple competitions.
- Different participant sets by competition.
- Date-range-filtered totals, today values, averages, daily series, leader, margin, and ranks.
- Existing `/api/v1/competition` compatibility.
- Participant sync response includes per-competition summaries.
- `/api/v1/sync/me` returns only memberships for the authenticated participant.

Dashboard tests:

- 0, 1, 2, 4, and 8 participants.
- Multiple active competitions.
- Competition selector URL state.
- Projection chart with participant visibility toggles.
- Last 14 Days grouped chart.
- Daily Winners across all participants.
- Mobile and desktop viewport checks.

iOS tests:

- Existing QR format.
- QR format with competition context.
- Same server/profile paired more than once.
- One server profile with multiple competitions.
- Multiple server profiles.
- Coalesced HealthKit date ranges.
- Token rotation re-pairing.

## Implementation Plan

### Phase 1: Backend Data Model

1. Add SQLite migration support.
2. Add `slug` and `status` to competitions.
3. Add `settings.default_competition_id`.
4. Add `competition_memberships`.
5. Migrate existing participants into `default`.
6. Stop overwriting existing competitions from Home Assistant options on every startup.
7. Add competition CRUD endpoints.
8. Add membership CRUD endpoints.
9. Update competition-state aggregation by competition ID and date range.
10. Add `/api/v1/competitions` and `/api/v1/competitions/{competition_id}/state`.
11. Add `/api/v1/sync/me`.
12. Update sync response with per-competition summaries.

### Phase 2: Dashboard

1. Add competition switcher.
2. Fetch selected competition state.
3. Keep participant cards all-member.
4. Replace projection chart with multi-participant projection mode selector.
5. Replace Last 14 Days diverging chart with grouped multi-participant chart.
6. Update Daily Winners heatmap to all participants.
7. Add visibility toggles for larger competitions.
8. Add desktop and mobile visual verification for 0, 1, 2, 4, and 8 participants.

### Phase 3: Admin UI

1. Add competition list.
2. Add create/edit/archive/restore competition forms.
3. Add default competition selector.
4. Add membership management.
5. Add existing-participant picker.
6. Add membership override editing.
7. Add competition-context pairing QR generation.

### Phase 4: iOS

1. Replace single connection storage with server profiles.
2. Store tokens in Keychain.
3. Add joined competition storage.
4. Update QR pairing parser for optional competition context.
5. Add `/sync/me` discovery.
6. Update full sync to use coalesced date ranges.
7. Update background sync to handle multiple profiles and competitions.
8. Add local UI for joined competitions and per-competition sync status.

### Phase 5: Home Assistant Entities

1. Add competition-specific entity IDs.
2. Keep default competition legacy entity IDs.
3. Document entity changes.

## Acceptance Criteria

- Admin can create at least two active competitions with overlapping dates.
- Admin can add the same participant to multiple competitions.
- Admin can create two competitions with different participant sets.
- Existing installs migrate so all current participants are in the default competition.
- Existing Home Assistant competition options do not overwrite admin-edited competitions after migration.
- Dashboard can switch between competitions.
- Dashboard renders correctly with 0, 1, 2, 4, and 8 participants.
- Projection chart remains readable with 8 participants by using visibility controls.
- Last 14 Days chart compares more than two participants.
- Daily Winners considers all active competition participants by default.
- Competition totals are constrained to competition date ranges.
- iOS can pair one phone once and discover multiple joined competitions on that server.
- iOS can sync HealthKit data once for overlapping ranges and update multiple competition totals.
- Existing `/api/v1/competition` clients continue to work for the default competition.

## Open Questions

- Should competitions support recurrence templates, such as "every month", or should monthly competitions be explicit records?
- Should new competitions default to no members, all active participants, or a selected subset?
- Should a participant be able to pause syncing to one competition while continuing another?
- Should archived competitions remain visible to ordinary dashboard viewers through direct URLs?
- Should admins be able to hide specific active competitions from the public switcher?
