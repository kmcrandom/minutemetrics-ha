# Dashboard Spec

## Purpose

The dashboard is the main shared view for the competition. It should work as a Home Assistant app dashboard and as a standalone browser page served by the app.

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
- Admin shortcut for configured users.

## Projection Graph

The projection graph is a combined SVG chart for the top two ranked participants.

- Historical data is cumulative Exercise Minutes from competition start through local today.
- Historical lines are thick, solid, stepped lines in each participant's color.
- Future data starts after local today and runs through the configured competition end date.
- Each participant has three thinner projection lines:
  - all-data average: total minutes divided by elapsed competition days.
  - last 7 days average: average of the most recent seven local days.
  - today pace: current local day's minutes repeated for every remaining day.
- The graph includes a visible Today marker, y-axis minute labels, month ticks, and a legend.
- Projections are visual guidance only; stored data remains daily actual totals.

## Last 14 Days

The Last 14 Days chart compares the top two ranked participants.

- Most recent day appears at the top.
- Rank #1 extends left from the center axis.
- Rank #2 extends right from the center axis.
- Inline minute labels are not shown inside the bars.
- Hovering a bar row shows both participants' minutes for that date.
- A centered scale row shows approximate minutes.

## Daily Winners

The Daily Winners heatmap shows all synced days up to the viewer's local today.

- Each day is colored by the participant with more Exercise Minutes that day.
- Ties use a neutral color.
- Month labels group the visible days.
- Hovering a cell shows the date, winner/tie, and both participants' minutes.

## Data Fields

The dashboard consumes `GET /api/v1/competition`.

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
10. Add Playwright visual smoke tests for desktop and mobile widths.

## Acceptance Criteria

- Dashboard displays correctly with zero, one, two, and more than two participants.
- No labels or totals overlap at mobile widths.
- A first-run install with no participants or no synced data shows a polished empty state with setup steps.
- Participant display names and colors come from the API.
- Dashboard works whether participants are linked to Home Assistant users/persons or not.
- Stale data is visible within the first viewport.
- Dashboard can be embedded in Home Assistant.
