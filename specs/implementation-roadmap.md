# Implementation Roadmap

## Spec-Driven Development Workflow

Each deliverable should move through the same stages:

1. Confirm requirements and acceptance criteria.
2. Update the relevant spec before or alongside code changes.
3. Build the smallest vertical slice.
4. Add tests for the behavior described in the spec.
5. Verify against real Apple Health and Home Assistant behavior.
6. Package and document the deliverable for reuse.

Any user-visible behavior change should update the corresponding spec in the same work cycle. Specs are split by deliverable: iOS app, Home Assistant app, API/data model, dashboard, packaging/distribution, and verification.

The first production-quality milestone should prove the full data path:

```text
HealthKit Exercise Minutes -> iOS sync payload -> Home Assistant app SQLite -> aggregate API -> dashboard total
```

## Milestone 1: Shared Contract

Deliverables:

- API schema.
- SQLite schema.
- Competition and participant model.
- Sync payload format.

Exit criteria:

- Contract supports arbitrary participants.
- Contract supports optional Home Assistant user/person links without making them required identity.
- Daily totals can be upserted idempotently.
- Aggregates can be calculated for zero, one, two, and many participants.

## Milestone 2: Home Assistant App API

Deliverables:

- FastAPI service.
- SQLite migrations.
- Participant admin endpoints.
- Optional Home Assistant user/person link fields.
- Sync endpoint.
- Competition aggregate endpoint.

Exit criteria:

- Home Assistant app accepts authenticated token-only sync payloads.
- Home Assistant app persists data across restarts.
- Home Assistant app returns correct totals and rankings.

## Milestone 3: iOS Accuracy Prototype

Deliverables:

- SwiftUI app shell.
- HealthKit permission flow.
- Exercise Minutes query service.
- Local total display.
- Manual full sync.

Exit criteria:

- Local app total matches Apple Health Exercise Minutes for the selected range.
- App can sync to the local backend and Home Assistant app.
- Sync response total matches local total.

## Milestone 4: Dashboard

Deliverables:

- Competition scoreboard.
- Participant totals.
- Projection graph.
- Last 14 days diverging comparison.
- Daily winners heatmap.
- Stale sync state.

Exit criteria:

- Dashboard is usable inside Home Assistant.
- Display works with more than two participants.
- Stale or missing participant data is obvious.

## Milestone 5: Home Assistant Entities

Deliverables:

- Participant total sensors.
- Participant today sensors.
- Leader sensor.
- Margin sensor.
- Sync health attributes.

Exit criteria:

- Home Assistant state updates after sync.
- Entity names are generated from participant configuration.
- Entities remain stable when display names change.
- Entities remain stable when Home Assistant links are added, changed, or removed.

## Milestone 6: Packaging

Deliverables:

- Home Assistant app repository layout.
- Home Assistant app documentation.
- iOS build and TestFlight notes.
- Setup, validation, and troubleshooting guides.

Exit criteria:

- A new user can install and configure the system without code edits.
- Documentation explains HealthKit permission, privacy, and validation.

## Milestone 7: Public Beta

Deliverables:

- Release notes.
- Known limitations.
- Issue templates.
- Example dashboard screenshots.

Exit criteria:

- At least one clean install has been tested.
- At least two participant devices have synced real HealthKit data.
- Manual Apple Health validation passes for each participant.
