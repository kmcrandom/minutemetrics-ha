# Product Requirements

## Problem

Apple Health can show Exercise Minutes, but it does not provide a convenient year-to-date competition view across multiple people. Home Assistant companion sensors do not currently expose the same Exercise Minutes total visible in Apple Health.

MinuteMetrics solves this by letting each participant authorize an iOS app to read their Apple Health Exercise Minutes and sync daily totals into a shared local service.

## Users

- Participants who wear an Apple Watch and want to compare exercise-minute totals.
- A household administrator who configures Home Assistant, participants, tokens, and dashboard visibility.
- Optional viewers who only need to see the scoreboard.

## Goals

- Accurately reflect Apple Health Exercise Minutes for each participant.
- Support arbitrary participant display names and colors.
- Optionally link participants to Home Assistant users or persons without requiring that link.
- Support a configurable competition period, with year-to-date as the default.
- Provide a polished Home Assistant view.
- Provide enough local app UI to sync, validate, and view personal totals.
- Package the project so other Home Assistant users can install and configure it.

## Non-Goals

- Do not scrape Apple Health exports.
- Do not require iCloud account sharing.
- Do not infer Exercise Minutes from steps, workouts, calories, or distance.
- Do not depend on hardcoded participant names.
- Do not require competition participants to have Home Assistant user accounts.
- Do not require Home Assistant if a user only wants the iOS app display, though Home Assistant is the primary shared view.
- Do not support Android health data in the initial release.

## Success Criteria

- A participant's total matches Apple Health Exercise Minutes for the selected period after a full resync.
- Multiple participants can be added without code changes.
- A participant can be linked, unlinked, or relinked to a Home Assistant user/person without changing historical data.
- A stale or missing participant sync is visible in the dashboard.
- The dashboard clearly shows leader, totals, margin, daily history, and sync health.
- The project can be installed and configured by another user from documented steps.

## Key Decisions

- The iOS app is the source of truth for Apple Health reads because HealthKit requires local, permissioned access on each phone.
- The Home Assistant app is the source of truth for shared aggregation and dashboard rendering.
- Daily totals are stored instead of only cumulative totals so late edits, charts, and audit views are possible.
