# Dashboard Spec

## Purpose

The dashboard is the main shared view for exercise-minute competitions. It should work as a Home Assistant ingress dashboard and as a standalone browser page served by the app.

## Requirements

- Responsive layout for wall display, tablet, desktop, and phone.
- Clear competition title and date range.
- Participant totals.
- Current leader.
- Margin between first and second place.
- Today's Exercise Minutes per participant.
- Last 14 days diverging bar comparison for the top two participants.
- Daily winner heatmap for all synced days up to the viewer's local today.
- Dedicated projection graph for the top two participants.
- Stale sync warning.
- Neutral empty states before participants sync.
- Dashboard assets must use relative paths so the page works under Home Assistant ingress subpaths.
- Configurable participant names and colors.
- Optional Home Assistant user/person linkage display when configured.
- Dashboard data must be private. Loading the shell without a valid dashboard data context must not reveal competition data.
- Home Assistant ingress viewers receive full dashboard access after Home Assistant authentication.
- Standalone full-dashboard access uses a configured dashboard token.
- iOS or participant-scoped dashboard access uses the participant sync token and only lists competitions assigned to that participant.

## Visual Priorities

Top section:

- Competition title.
- Leader.
- Lead margin.
- Large participant totals.
- Compact today and daily-average stats to the right of each participant's name/total on wide screens.

Middle section:

- Projection graph.
- Last 14 days comparison chart.

Lower section:

- Daily winners heatmap with month labels.
- Sync status.
- Private-data empty or authorization state when the viewer is not authorized.

## Projection Graph

The projection graph is a combined SVG chart for all active participants in the selected competition.

- Historical data is cumulative Exercise Minutes from competition start through local today.
- Historical lines are thick, solid, stepped lines in each participant's color.
- Future data starts after local today and runs through the configured competition end date.
- Each participant has three thinner projection lines:
  - Average pace: total minutes divided by elapsed competition days.
  - Weekly pace: average of the most recent seven local days.
  - Today's pace: current local day's minutes repeated for every remaining day.
- The graph includes a visible Today marker, y-axis minute labels, month ticks, and a legend.
- Projection labels use the exact display text "Today's pace", "Weekly pace", and "Average pace".
- Hovering, tapping, or keyboard-focusing each projection label or line shows a popup with the projected total minutes that participant would have at the end of the competition if they kept that pace.
- Projection popups are accessible on touch devices and dismiss when focus moves away, the user taps another projection, or the user closes the popup.
- Projections are visual guidance only; stored data remains daily actual totals.

## Last 14 Days

The Last 14 Days chart compares all active participants in the selected competition.

- Most recent day appears at the top.
- Each participant receives a proportional horizontal bar for that day.
- Inline minute labels are not shown inside the bars.
- Hovering, tapping, or keyboard-focusing a bar row shows all participant minutes for that date.
- A centered scale row shows approximate minutes.

## Daily Movers

The Daily Movers heatmap shows all synced days up to the viewer's local today.

- Each day is colored by the participant with the most Exercise Minutes that day.
- Ties use a neutral color.
- Month labels group the visible days.
- Hovering, tapping, or keyboard-focusing a cell shows the date, winner/tie, and all participant minutes.
- Color intensity is capped around 60 minutes so one outlier day does not mute the rest of the calendar.

## Data Fields

The dashboard consumes:

- `GET /api/v1/competitions`
- `GET /api/v1/competition`
- `GET /api/v1/competitions/{competition_id}/state`

All dashboard data requests require one of:

- Trusted Home Assistant ingress identity for all active competitions.
- Admin bearer token for all active competitions.
- Dashboard bearer token for all active competitions.
- Participant sync bearer token for only that participant's active competition memberships.

When the dashboard is opened outside Home Assistant, a token can be passed in the URL fragment, such as `#token=<token>`. The fragment keeps the token out of the HTTP request URL and allows the JavaScript client to send it as a bearer token.

Expected derived values:

- `total_minutes`
- `today_minutes`
- `days_synced`
- `average_daily_minutes`
- `last_synced_at`
- `is_stale`
- `rank`

## Accessibility

- Do not rely on color alone for participant identity.
- Use readable contrast.
- Show display names alongside colors.
- Use Home Assistant avatars or person names only as optional enhancements; MinuteMetrics display names remain sufficient on their own.
- Ensure the lead and total values remain understandable on small screens.

## Implementation Plan

1. Build static web app shell.
2. Add API client for competition state.
3. Add scoreboard component.
4. Add participant total components.
5. Add daily trend chart.
6. Add heatmap/calendar component.
7. Add projection graph.
8. Add stale-sync and error states.
9. Add responsive polish for Home Assistant iframe/webpage usage.
10. Add private dashboard data access.
11. Add Playwright visual smoke tests for desktop and mobile widths.

## Acceptance Criteria

- Dashboard displays correctly with zero, one, two, and more than two participants.
- No labels or totals overlap at mobile widths.
- A first-run install with no participants or no synced data shows a polished empty state with setup steps.
- Participant display names and colors come from the API.
- Dashboard works whether participants are linked to Home Assistant users/persons or not.
- Stale data is visible within the first viewport.
- Dashboard can be embedded in Home Assistant.
- Unauthenticated dashboard data requests return `401 Unauthorized`.
- A participant sync token can only list and view competitions where that participant is an active member.
- Projection legend labels read "Today's pace", "Weekly pace", and "Average pace".
- Each projection mode exposes a hover/tap/focus popup showing the participant's end-of-competition total minutes for that pace.
