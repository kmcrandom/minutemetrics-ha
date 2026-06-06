const state = {
  data: null,
};

const els = {
  title: document.querySelector("#title"),
  range: document.querySelector("#range"),
  leaderName: document.querySelector("#leaderName"),
  margin: document.querySelector("#margin"),
  participants: document.querySelector("#participants"),
  emptyState: document.querySelector("#emptyState"),
  projectionChart: document.querySelector("#projectionChart"),
  projectionLegend: document.querySelector("#projectionLegend"),
  bars: document.querySelector("#bars"),
  heatmap: document.querySelector("#heatmap"),
  refresh: document.querySelector("#refresh"),
  template: document.querySelector("#participantTemplate"),
};

els.refresh.addEventListener("click", () => load());

load();
setInterval(load, 60_000);

async function load() {
  try {
    const response = await fetch("api/v1/competition", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    render(state.data);
  } catch (error) {
    els.leaderName.textContent = "Unable to load";
    els.margin.textContent = "0 min";
    els.participants.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

function render(data) {
  const competition = data.competition;
  els.title.textContent = competition.name;
  els.range.textContent = `${formatDate(competition.start_date)} to ${formatDate(competition.end_date)}`;
  els.leaderName.textContent = data.leader ? data.leader.display_name : "Waiting for sync";
  els.margin.textContent = `${formatNumber(data.margin)} min`;
  els.emptyState.hidden = data.participants.length > 0;
  renderParticipants(data.participants);
  renderProjectionChart(data);
  renderBars(data);
  renderHeatmap(data);
}

function renderParticipants(participants) {
  els.participants.replaceChildren();
  if (!participants.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No participants synced yet.";
    els.participants.append(empty);
    return;
  }

  participants.forEach((participant) => {
    const node = els.template.content.cloneNode(true);
    node.querySelector(".swatch").style.background = participant.color;
    node.querySelector(".participant-name").textContent = `#${participant.rank} ${participant.display_name}`;
    const sync = node.querySelector(".sync");
    sync.textContent = participant.last_synced_at
      ? `Synced ${relativeTime(participant.last_synced_at)}`
      : "No sync yet";
    sync.classList.toggle("stale", participant.is_stale);
    node.querySelector(".total").textContent = `${formatNumber(participant.total_minutes)} min`;
    node.querySelector(".today").textContent = `${formatNumber(participant.today_minutes)} min`;
    node.querySelector(".average").textContent = `${participant.average_daily_minutes.toFixed(1)} min`;
    els.participants.append(node);
  });
}

function renderProjectionChart(data) {
  els.projectionChart.replaceChildren();
  els.projectionLegend.replaceChildren();

  const participants = data.participants.slice(0, 2);
  if (participants.length < 2) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Add a second participant to compare projections.";
    els.projectionChart.append(empty);
    return;
  }

  const start = data.competition.start_date;
  const today = minDateString(todayDateString(), data.competition.end_date);
  const end = data.competition.end_date;
  const allChartDates = dateRange(start, end);
  const todayIndex = Math.max(0, allChartDates.indexOf(today));

  const chartSeries = participants.map((participant) => buildParticipantProjection(data, participant, start, today, end));
  const maxY = niceScaleMax(
    Math.max(
      1,
      ...chartSeries.flatMap((series) => [
        ...series.history.map((point) => point.value),
        ...series.projections.flatMap((projection) => projection.points.map((point) => point.value)),
      ])
    )
  );

  const width = 960;
  const height = 360;
  const pad = { top: 18, right: 22, bottom: 42, left: 64 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const xForIndex = (index) => pad.left + (index / Math.max(1, allChartDates.length - 1)) * plotWidth;
  const yForValue = (value) => pad.top + plotHeight - (value / maxY) * plotHeight;
  const yTicks = [0, Math.round(maxY / 2), maxY];
  const xTicks = monthTicks(allChartDates);

  const svg = createSvg("svg", {
    class: "projection-svg",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": "Projected exercise minutes",
  });

  yTicks.forEach((tick) => {
    const y = yForValue(tick);
    svg.append(
      createSvg("line", { class: "projection-grid", x1: pad.left, y1: y, x2: width - pad.right, y2: y }),
      createSvg("text", { class: "projection-axis-label", x: pad.left - 10, y: y + 4, "text-anchor": "end" }, formatNumber(tick))
    );
  });

  xTicks.forEach((tick) => {
    const x = xForIndex(tick.index);
    svg.append(
      createSvg("line", { class: "projection-tick", x1: x, y1: pad.top, x2: x, y2: height - pad.bottom }),
      createSvg("text", { class: "projection-axis-label", x, y: height - 16, "text-anchor": "middle" }, tick.label)
    );
  });

  const todayX = xForIndex(todayIndex);
  svg.append(
    createSvg("line", { class: "projection-today", x1: todayX, y1: pad.top, x2: todayX, y2: height - pad.bottom }),
    createSvg("text", { class: "projection-today-label", x: todayX + 6, y: pad.top + 14 }, "Today")
  );

  chartSeries.forEach((series) => {
    const historyPath = createSvg("path", {
      class: "projection-line projection-history",
      d: stepPath(series.history, xForIndex, yForValue),
      stroke: series.participant.color,
    });
    historyPath.append(createSvg("title", {}, `${series.participant.display_name}: actual cumulative minutes`));
    svg.append(historyPath);

    series.projections.forEach((projection) => {
      const path = createSvg("path", {
        class: `projection-line projection-future ${projection.className}`,
        d: stepPath(projection.points, xForIndex, yForValue),
        stroke: series.participant.color,
      });
      path.append(
        createSvg(
          "title",
          {},
          `${series.participant.display_name} projected by ${projection.label}: ${formatNumber(Math.round(projection.points[projection.points.length - 1].value))} min`
        )
      );
      svg.append(path);
    });
  });

  els.projectionChart.append(svg);
  renderProjectionLegend(chartSeries);
}

function buildParticipantProjection(data, participant, start, today, end) {
  const dates = dateRange(start, today);
  let cumulative = 0;
  const history = dates.map((date, index) => {
    cumulative += minutesFor(data, participant.id, date);
    return { index, date, value: cumulative };
  });
  const futureDates = dateRange(addDays(today, 1), end);
  const futureStartIndex = dates.length - 1;
  const elapsedDays = Math.max(1, dates.length);
  const lastSevenDates = dates.slice(-7);
  const totalAverage = cumulative / elapsedDays;
  const lastSevenAverage =
    lastSevenDates.reduce((sum, date) => sum + minutesFor(data, participant.id, date), 0) / Math.max(1, lastSevenDates.length);
  const todayMinutes = minutesFor(data, participant.id, today);
  const rates = [
    { label: "all-data average", className: "projection-total-average", value: totalAverage },
    { label: "last 7 days", className: "projection-seven-average", value: lastSevenAverage },
    { label: "today's minutes", className: "projection-today-rate", value: todayMinutes },
  ];

  const projections = rates.map((rate) => ({
    ...rate,
    points: [
      { index: futureStartIndex, date: today, value: cumulative },
      ...futureDates.map((date, futureIndex) => ({
        index: futureStartIndex + futureIndex + 1,
        date,
        value: cumulative + rate.value * (futureIndex + 1),
      })),
    ],
  }));

  return { participant, history, projections };
}

function renderProjectionLegend(series) {
  const people = document.createElement("div");
  people.className = "projection-people";
  series.forEach(({ participant }) => {
    const item = document.createElement("span");
    item.innerHTML = `<i style="background:${participant.color}"></i>${escapeHtml(participant.display_name)}`;
    people.append(item);
  });

  const styles = document.createElement("div");
  styles.className = "projection-styles";
  styles.innerHTML = `
    <span><i class="legend-line history"></i>Actual</span>
    <span><i class="legend-line total-average"></i>All-data avg</span>
    <span><i class="legend-line seven-average"></i>Last 7 days</span>
    <span><i class="legend-line today-rate"></i>Today pace</span>
  `;

  els.projectionLegend.append(people, styles);
}

function renderBars(data) {
  els.bars.replaceChildren();
  const participants = data.participants.slice(0, 2);
  if (participants.length < 2) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Add a second participant to compare daily minutes.";
    els.bars.append(empty);
    return;
  }
  const dates = lastDates(data.daily_series, 14);
  const max = Math.max(
    1,
    ...dates.flatMap((date) => participants.map((participant) => minutesFor(data, participant.id, date)))
  );
  const scaleMax = niceScaleMax(max);
  renderBarScale(participants, scaleMax);

  dates.toReversed().forEach((date) => {
    const row = document.createElement("div");
    row.className = "bar-row";

    const label = document.createElement("div");
    label.className = "bar-label";
    label.textContent = shortDate(date);

    const track = document.createElement("div");
    track.className = "bar-track diverging";

    const leftMinutes = minutesFor(data, participants[0].id, date);
    const rightMinutes = minutesFor(data, participants[1].id, date);
    const tooltip = [
      shortDate(date),
      `${participants[0].display_name}: ${formatNumber(leftMinutes)} min`,
      `${participants[1].display_name}: ${formatNumber(rightMinutes)} min`,
    ].join("\n");
    row.title = tooltip;
    track.title = tooltip;

    const leftFill = document.createElement("div");
    leftFill.className = "bar-fill bar-fill-left";
    leftFill.style.width = `${(leftMinutes / scaleMax) * 50}%`;
    leftFill.style.background = participants[0].color;
    leftFill.title = tooltip;

    const rightFill = document.createElement("div");
    rightFill.className = "bar-fill bar-fill-right";
    rightFill.style.width = `${(rightMinutes / scaleMax) * 50}%`;
    rightFill.style.background = participants[1].color;
    rightFill.title = tooltip;

    track.append(leftFill, rightFill);
    row.append(label, track);
    els.bars.append(row);
  });
}

function renderBarScale(participants, scaleMax) {
  const row = document.createElement("div");
  row.className = "bar-row bar-scale-row";

  const label = document.createElement("div");
  label.className = "bar-label";
  label.textContent = "Minutes";

  const scale = document.createElement("div");
  scale.className = "bar-scale";
  scale.innerHTML = `
    <span>${formatNumber(scaleMax)}</span>
    <span>${formatNumber(Math.round(scaleMax / 2))}</span>
    <span>0</span>
    <span>${formatNumber(Math.round(scaleMax / 2))}</span>
    <span>${formatNumber(scaleMax)}</span>
  `;
  scale.title = `${participants[0].display_name} extends left; ${participants[1].display_name} extends right.`;

  row.append(label, scale);
  els.bars.append(row);
}

function renderHeatmap(data) {
  els.heatmap.replaceChildren();
  const participants = data.participants.slice(0, 2);
  if (participants.length < 2) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Add a second participant to compare daily winners.";
    els.heatmap.append(empty);
    return;
  }
  const today = todayDateString();
  const dates = allDates(data.daily_series).filter((date) => date <= today);
  const max = Math.max(
    1,
    ...dates.flatMap((date) => participants.map((participant) => minutesFor(data, participant.id, date)))
  );
  const days = dates.map((date) => {
    const firstMinutes = minutesFor(data, participants[0].id, date);
    const secondMinutes = minutesFor(data, participants[1].id, date);
    return {
      date,
      firstMinutes,
      secondMinutes,
      winner:
        firstMinutes === secondMinutes
          ? null
          : firstMinutes > secondMinutes
            ? participants[0]
            : participants[1],
      winningMinutes: Math.max(firstMinutes, secondMinutes),
    };
  });
  const months = groupByMonth(days);
  months.forEach((month) => {
    const group = document.createElement("section");
    group.className = "heat-month";

    const label = document.createElement("h3");
    label.className = "heat-month-label";
    label.textContent = month.label;

    const cells = document.createElement("div");
    cells.className = "heat-month-cells";
    month.days.forEach((day) => {
      const cell = document.createElement("div");
      cell.className = "heat-cell";
      const alpha = Math.max(0.16, day.winningMinutes / max);
      cell.style.background = day.winner ? colorWithAlpha(day.winner.color, alpha) : "var(--line)";
      cell.title = [
        formatDate(day.date),
        day.winner ? `Winner: ${day.winner.display_name}` : "Tie",
        `${participants[0].display_name}: ${formatNumber(day.firstMinutes)} min`,
        `${participants[1].display_name}: ${formatNumber(day.secondMinutes)} min`,
      ].join("\n");
      cells.append(cell);
    });

    group.append(label, cells);
    els.heatmap.append(group);
  });
}

function allDates(seriesByParticipant) {
  const dates = new Set();
  Object.values(seriesByParticipant).forEach((series) => {
    series.forEach((day) => dates.add(day.date));
  });
  return [...dates].sort();
}

function groupByMonth(series) {
  const groups = [];
  series.forEach((day) => {
    const monthKey = day.date.slice(0, 7);
    let group = groups.at(-1);
    if (!group || group.key !== monthKey) {
      group = {
        key: monthKey,
        label: new Intl.DateTimeFormat(undefined, { month: "short" }).format(parseDateOnly(day.date)),
        days: [],
      };
      groups.push(group);
    }
    group.days.push(day);
  });
  return groups;
}

function minutesFor(data, participantId, date) {
  const day = (data.daily_series[participantId] || []).find((item) => item.date === date);
  return day ? day.exercise_minutes : 0;
}

function createSvg(tagName, attributes = {}, text = "") {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tagName);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  if (text) {
    element.textContent = text;
  }
  return element;
}

function stepPath(points, xForIndex, yForValue) {
  if (!points.length) return "";
  const commands = [`M ${xForIndex(points[0].index).toFixed(2)} ${yForValue(points[0].value).toFixed(2)}`];
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const x = xForIndex(current.index).toFixed(2);
    const previousY = yForValue(previous.value).toFixed(2);
    const y = yForValue(current.value).toFixed(2);
    commands.push(`H ${x}`, `V ${y}`);
  }
  return commands.join(" ");
}

function dateRange(start, end) {
  if (!start || !end || start > end) return [];
  const dates = [];
  let cursor = parseDateOnly(start);
  const last = parseDateOnly(end);
  while (cursor <= last) {
    dates.push(dateString(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return dates;
}

function addDays(value, days) {
  const date = parseDateOnly(value);
  date.setDate(date.getDate() + days);
  return dateString(date);
}

function monthTicks(dates) {
  const ticks = [];
  let currentMonth = "";
  dates.forEach((date, index) => {
    const month = date.slice(0, 7);
    if (month !== currentMonth) {
      currentMonth = month;
      ticks.push({
        index,
        label: new Intl.DateTimeFormat(undefined, { month: "short" }).format(parseDateOnly(date)),
      });
    }
  });
  return ticks;
}

function minDateString(first, second) {
  return first < second ? first : second;
}

function lastDates(seriesByParticipant, count) {
  const dates = new Set();
  const today = todayDateString();
  Object.values(seriesByParticipant).forEach((series) => {
    series.forEach((day) => {
      if (day.date <= today) {
        dates.add(day.date);
      }
    });
  });
  return [...dates].sort().slice(-count);
}

function todayDateString() {
  return dateString(new Date());
}

function dateString(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function niceScaleMax(value) {
  if (value <= 0) return 10;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  const niceNormalized = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return niceNormalized * magnitude;
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(
    parseDateOnly(value)
  );
}

function shortDate(value) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(parseDateOnly(value));
}

function parseDateOnly(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function relativeTime(value) {
  const date = new Date(value);
  const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
  const units = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, seconds] of units) {
    if (Math.abs(diffSeconds) >= seconds) {
      return formatter.format(Math.round(diffSeconds / seconds), unit);
    }
  }
  return "just now";
}

function colorWithAlpha(hex, alpha) {
  const clean = hex.replace("#", "");
  if (clean.length !== 6) return hex;
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  })[char]);
}
