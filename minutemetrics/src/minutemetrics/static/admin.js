const state = {
  appConfig: null,
  competitions: [],
  participants: [],
  memberships: [],
};

const DEFAULT_COLORS = [
  "#2563eb",
  "#7c3aed",
  "#db2777",
  "#dc2626",
  "#ea580c",
  "#ca8a04",
  "#eab308",
  "#16a34a",
  "#0891b2",
  "#0f766e",
];

const els = {
  gate: document.querySelector("#adminGate"),
  tokenForm: document.querySelector("#tokenForm"),
  adminToken: document.querySelector("#adminToken"),
  status: document.querySelector("#adminStatus"),
  workspace: document.querySelector("#adminWorkspace"),
  view: document.querySelector("#adminView"),
  clearAdminToken: document.querySelector("#clearAdminToken"),
  clearData: document.querySelector("#clearData"),
  pairingDialog: document.querySelector("#pairingDialog"),
  pairingTitle: document.querySelector("#pairingTitle"),
  qrFrame: document.querySelector("#qrFrame"),
  closePairing: document.querySelector("#closePairing"),
};

els.adminToken.value = sessionStorage.getItem("minutemetrics.adminToken") || "";
els.tokenForm.addEventListener("submit", (event) => unlock(event));
els.clearAdminToken.addEventListener("click", () => clearAdminToken());
els.clearData.addEventListener("click", () => clearSyncData());
els.closePairing.addEventListener("click", () => els.pairingDialog.close());
window.addEventListener("hashchange", () => renderRoute());

loadAppConfig().then(() => {
  if (els.adminToken.value.trim()) {
    loadAdminData();
  }
});

async function loadAppConfig() {
  const response = await fetch("api/v1/app-config", { cache: "no-store" });
  if (response.ok) {
    state.appConfig = await response.json();
  }
}

async function unlock(event) {
  event.preventDefault();
  await loadAdminData();
}

async function loadAdminData() {
  const token = adminToken();
  if (!token) return;
  setStatus("Loading admin data...");
  try {
    const [competitions, participants] = await Promise.all([
      fetchJson("api/v1/admin/competitions?include_archived=true"),
      fetchJson("api/v1/admin/participants"),
    ]);
    sessionStorage.setItem("minutemetrics.adminToken", token);
    state.competitions = competitions;
    state.participants = participants;
    els.gate.hidden = true;
    els.workspace.hidden = false;
    renderRoute();
    setStatus(`Loaded ${competitions.length} competition${competitions.length === 1 ? "" : "s"}.`);
  } catch (error) {
    els.gate.hidden = false;
    els.workspace.hidden = true;
    setStatus(error.message, true);
  }
}

function renderRoute() {
  if (els.workspace.hidden) return;
  const route = location.hash.replace(/^#\/?/, "");
  if (!route) {
    renderOverview();
    return;
  }
  if (route === "competitions/new") {
    renderCompetitionNew();
    return;
  }
  if (route.startsWith("competitions/")) {
    renderCompetitionDetail(route.split("/")[1]);
    return;
  }
  if (route.startsWith("participants/")) {
    renderParticipantDetail(route.split("/")[1]);
    return;
  }
  navigate("");
}

function renderOverview() {
  const section = el("section", { className: "admin-pages" }, [
    panel([
      panelHead("Competitions"),
      table(
        ["Name", "Date range"],
        state.competitions,
        (competition) => [
          cellLink(competition.name, `#/competitions/${competition.id}`),
          formatDateRange(competition),
        ],
        "No competitions yet."
      ),
      el("div", { className: "table-actions" }, [
        el("a", { className: "primary-button", href: "#/competitions/new" }, ["Add Competition"]),
      ]),
    ]),
    panel([
      panelHead("All Participants"),
      table(
        ["Name", "Color"],
        state.participants,
        (participant) => [
          cellLink(participant.display_name, `#/participants/${participant.id}`),
          colorCell(participant.color),
        ],
        "No participants yet."
      ),
    ]),
  ]);
  setView(section);
}

function renderCompetitionNew() {
  const form = competitionForm({}, "Create");
  form.addEventListener("submit", (event) => createCompetition(event, form));
  setView(panel([
    pageHead("Add Competition", "Create a new competition and then add participants from its detail page."),
    form,
  ]));
}

function renderCompetitionDetail(competitionId) {
  const competition = state.competitions.find((item) => item.id === competitionId);
  if (!competition) {
    renderMissing("Competition not found.");
    return;
  }
  state.memberships = [];
  loadCompetitionDetail(competition).catch((error) => setStatus(error.message, true));
}

async function loadCompetitionDetail(competition) {
  state.memberships = await fetchJson(`api/v1/admin/competitions/${competition.id}/participants`);
  const form = competitionForm(competition, "Save");
  form.addEventListener("submit", (event) => updateCompetition(event, competition, form));

  setView(el("section", { className: "admin-pages" }, [
    panel([
      pageHead(competition.name, "Edit competition details, status, and participants."),
      form,
      el("div", { className: "admin-actions detail-actions" }, [
        el("button", {
          className: "secondary-button",
          type: "button",
          disabled: competition.is_default,
          onclick: () => setDefaultCompetition(competition),
        }, ["Make Default"]),
        el("button", {
          className: "danger-button",
          type: "button",
          onclick: () => toggleArchiveCompetition(competition),
        }, [competition.status === "archived" ? "Restore" : "Archive"]),
      ]),
    ]),
    panel([
      panelHead("Competition Participants"),
      memberAddForm(competition),
      membersTable(competition),
    ]),
    backLink(),
  ]));
}

function renderParticipantDetail(participantId) {
  const participant = state.participants.find((item) => item.id === participantId);
  if (!participant) {
    renderMissing("Participant not found.");
    return;
  }
  const form = el("form", { className: "admin-form participant-detail-form" }, [
    labeledInput("Name", "participantName", "text", participant.display_name, { required: true }),
    colorPicker("Color", "participantColor", participant.color),
    labeledInput("Home Assistant user ID", "haUser", "text", participant.home_assistant_user_id || ""),
    labeledInput("Home Assistant person entity", "haPerson", "text", participant.home_assistant_person_entity_id || ""),
    el("button", { className: "primary-button", type: "submit" }, ["Save"]),
  ]);
  form.addEventListener("submit", (event) => updateParticipant(event, participant, form));

  setView(panel([
    pageHead(participant.display_name, "Edit participant identity, pairing, and Home Assistant links."),
    form,
    el("div", { className: "admin-actions detail-actions" }, [
      el("button", { className: "secondary-button", type: "button", onclick: () => rotateAndShowPairingQR(participant) }, ["Pair"]),
      el("button", { className: "danger-button", type: "button", onclick: () => deleteParticipant(participant) }, ["Delete"]),
    ]),
    syncText(participant.last_synced_at ? `Last synced ${relativeTime(participant.last_synced_at)}` : "No sync yet"),
    backLink(),
  ]));
}

function competitionForm(competition, buttonText) {
  return el("form", { className: "admin-form competition-detail-form" }, [
    labeledInput("Name", "competitionName", "text", competition.name || "", { required: true }),
    labeledInput("Slug", "competitionSlug", "text", competition.slug || ""),
    labeledInput("Start date", "competitionStart", "date", competition.start_date || "", { required: true }),
    labeledInput("End date", "competitionEnd", "date", competition.end_date || "", { required: true }),
    el("button", { className: "primary-button", type: "submit" }, [buttonText]),
  ]);
}

function memberAddForm(competition) {
  const form = el("form", { className: "admin-form member-create-form" });
  const existing = el("select", { name: "existingParticipant" }, [option("", "Create new participant")]);
  state.participants
    .filter((participant) => !state.memberships.some((membership) => membership.participant_id === participant.id))
    .forEach((participant) => existing.append(option(participant.id, participant.display_name)));
  const name = labeledInput("Name", "memberName", "text", "", {});
  const color = colorPicker("Color", "memberColor", DEFAULT_COLORS[0]);
  const presets = colorPresets(color.querySelector("input"));
  existing.addEventListener("change", () => {
    const participant = state.participants.find((item) => item.id === existing.value);
    name.querySelector("input").value = participant?.display_name || "";
    color.querySelector("input").value = participant?.color || DEFAULT_COLORS[0];
    updatePresetSelection(presets, color.querySelector("input").value);
  });
  form.append(labelWrap("Existing participant", existing), name, color, presets, el("button", { className: "primary-button", type: "submit" }, ["Add"]));
  form.addEventListener("submit", (event) => addMember(event, competition, form));
  return form;
}

function membersTable(competition) {
  if (!state.memberships.length) {
    return el("div", { className: "empty" }, ["No participants in this competition yet."]);
  }
  const rows = state.memberships.map((membership) => memberRow(competition, membership));
  return el("div", { className: "responsive-table" }, [
    el("table", { className: "admin-table member-edit-table" }, [
      el("thead", {}, [el("tr", {}, ["Name", "Color", "Active", "Last sync", ""].map((heading) => el("th", {}, [heading])))]),
      el("tbody", {}, rows),
    ]),
  ]);
}

function memberRow(competition, membership) {
  const name = el("input", {
    type: "text",
    value: membership.display_name_override || membership.participant_display_name,
    placeholder: membership.participant_display_name,
    "aria-label": "Participant name override",
  });
  const color = el("input", {
    type: "color",
    value: membership.color_override || membership.participant_color,
    "aria-label": "Participant color override",
  });
  const active = el("input", {
    type: "checkbox",
    checked: membership.active,
    "aria-label": "Active",
  });
  return el("tr", {}, [
    el("td", {}, [name]),
    el("td", {}, [color]),
    el("td", {}, [active]),
    el("td", {}, [membership.last_synced_at ? relativeTime(membership.last_synced_at) : "No sync yet"]),
    el("td", { className: "row-actions" }, [
      el("button", { className: "secondary-button", type: "button", onclick: () => updateMember(competition, membership, name, color, active) }, ["Save"]),
      el("button", { className: "danger-button", type: "button", onclick: () => removeMember(competition, membership) }, ["Remove"]),
    ]),
  ]);
}

async function createCompetition(event, form) {
  event.preventDefault();
  const name = form.elements.competitionName.value.trim();
  const slug = normalizeSlug(form.elements.competitionSlug.value.trim() || name);
  if (!name) return;
  setStatus(`Creating ${name}...`);
  try {
    const body = await fetchJson("api/v1/admin/competitions", {
      method: "POST",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        name,
        slug,
        start_date: form.elements.competitionStart.value,
        end_date: form.elements.competitionEnd.value,
      }),
    });
    await loadAdminData();
    navigate(`competitions/${body.id}`);
    setStatus(`Created ${body.name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function updateCompetition(event, competition, form) {
  event.preventDefault();
  const name = form.elements.competitionName.value.trim();
  const slug = normalizeSlug(form.elements.competitionSlug.value.trim());
  if (!name || !slug) return;
  setStatus(`Saving ${competition.name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/competitions/${competition.id}`, {
      method: "PATCH",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        name,
        slug,
        start_date: form.elements.competitionStart.value,
        end_date: form.elements.competitionEnd.value,
      }),
    });
    await loadAdminData();
    navigate(`competitions/${body.id}`);
    setStatus(`Saved ${body.name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function setDefaultCompetition(competition) {
  setStatus(`Setting ${competition.name} as default...`);
  try {
    await fetchJson(`api/v1/admin/competitions/${competition.id}/default`, { method: "POST" });
    await loadAdminData();
    navigate(`competitions/${competition.id}`);
    setStatus(`${competition.name} is now the default.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function toggleArchiveCompetition(competition) {
  const verb = competition.status === "archived" ? "restore" : "archive";
  if (!confirm(`${verb === "archive" ? "Archive" : "Restore"} ${competition.name}?`)) return;
  setStatus(`${verb === "archive" ? "Archiving" : "Restoring"} ${competition.name}...`);
  try {
    await fetchJson(`api/v1/admin/competitions/${competition.id}/${verb}`, { method: "POST" });
    await loadAdminData();
    navigate(`competitions/${competition.id}`);
    setStatus(`${competition.name} ${verb === "archive" ? "archived" : "restored"}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function addMember(event, competition, form) {
  event.preventDefault();
  const participantId = form.elements.existingParticipant.value || null;
  const displayName = form.elements.memberName.value.trim();
  if (!participantId && !displayName) return;
  setStatus(`Adding participant to ${competition.name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/competitions/${competition.id}/participants`, {
      method: "POST",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(
        participantId
          ? { participant_id: participantId }
          : { display_name: displayName, color: form.elements.memberColor.value }
      ),
    });
    if (body.sync_token) {
      await showPairingQR(body.display_name, body.sync_token);
    }
    await loadAdminData();
    navigate(`competitions/${competition.id}`);
    setStatus(`Added ${body.display_name} to ${competition.name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function updateMember(competition, membership, nameInput, colorInput, activeInput) {
  setStatus(`Saving ${membership.display_name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/competitions/${competition.id}/participants/${membership.participant_id}`, {
      method: "PATCH",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        display_name_override: nameInput.value.trim() === membership.participant_display_name
          ? null
          : nameInput.value.trim() || null,
        color_override: colorInput.value === membership.participant_color ? null : colorInput.value || null,
        active: activeInput.checked,
      }),
    });
    await loadAdminData();
    navigate(`competitions/${competition.id}`);
    setStatus(`Saved ${body.display_name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function removeMember(competition, membership) {
  if (!confirm(`Remove ${membership.display_name} from ${competition.name}? Their synced Health data will remain.`)) return;
  setStatus(`Removing ${membership.display_name}...`);
  try {
    await fetchJson(`api/v1/admin/competitions/${competition.id}/participants/${membership.participant_id}`, {
      method: "DELETE",
    });
    await loadAdminData();
    navigate(`competitions/${competition.id}`);
    setStatus(`Removed ${membership.display_name} from ${competition.name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function updateParticipant(event, participant, form) {
  event.preventDefault();
  const displayName = form.elements.participantName.value.trim();
  if (!displayName) return;
  setStatus(`Saving ${participant.display_name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/participants/${participant.id}`, {
      method: "PATCH",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        display_name: displayName,
        color: form.elements.participantColor.value,
      }),
    });
    await fetchJson(`api/v1/admin/participants/${participant.id}/home-assistant-link`, {
      method: "PATCH",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        home_assistant_user_id: form.elements.haUser.value.trim() || null,
        home_assistant_person_entity_id: form.elements.haPerson.value.trim() || null,
      }),
    });
    await loadAdminData();
    navigate(`participants/${body.id}`);
    setStatus(`Saved ${body.display_name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function rotateAndShowPairingQR(participant) {
  if (!confirm(`Create a new pairing code for ${participant.display_name}? The previous iPhone sync token will stop working.`)) return;
  setStatus(`Creating pairing code for ${participant.display_name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/participants/${participant.id}/rotate-token`, { method: "POST" });
    await showPairingQR(participant.display_name, body.sync_token);
    setStatus(`Pairing code ready for ${participant.display_name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function deleteParticipant(participant) {
  if (!confirm(`Delete ${participant.display_name} and all of their synced data?`)) return;
  setStatus(`Deleting ${participant.display_name}...`);
  try {
    await fetchJson(`api/v1/admin/participants/${participant.id}`, { method: "DELETE" });
    await loadAdminData();
    navigate("");
    setStatus(`Deleted ${participant.display_name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function clearSyncData() {
  if (!confirm("Clear all synced exercise data and sync history? Participants and pairing tokens will remain.")) return;
  setStatus("Clearing sync data...");
  try {
    const body = await fetchJson("api/v1/admin/data", { method: "DELETE" });
    await loadAdminData();
    setStatus(`Cleared ${body.deleted_exercise_days} exercise day${body.deleted_exercise_days === 1 ? "" : "s"}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function clearAdminToken() {
  sessionStorage.removeItem("minutemetrics.adminToken");
  els.adminToken.value = "";
  els.gate.hidden = false;
  els.workspace.hidden = true;
  setStatus("Admin token cleared.");
}

async function showPairingQR(displayName, syncToken) {
  const response = await fetch("api/v1/admin/pairing-qr", {
    method: "POST",
    headers: adminHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ server_url: pairingServerUrl(), sync_token: syncToken }),
  });
  if (!response.ok) {
    const body = await readJson(response);
    throw new Error(body.detail || `Unable to generate QR code (${response.status})`);
  }
  const svg = await response.text();
  els.pairingTitle.textContent = displayName;
  els.qrFrame.innerHTML = svg;
  els.pairingDialog.showModal();
}

function table(headings, rows, rowCells, emptyMessage) {
  if (!rows.length) {
    return el("div", { className: "empty" }, [emptyMessage]);
  }
  const bodyRows = rows.map((row) => {
    const cells = rowCells(row);
    const link = cells.find((cell) => cell instanceof HTMLElement && cell.matches("a[href]"));
    const tr = el("tr", link ? {
      className: "clickable-row",
      tabIndex: 0,
      onclick: (event) => {
        if (event.target.closest("a, button, input, select, textarea")) return;
        link.click();
      },
      onkeydown: (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        link.click();
      },
    } : {}, cells.map((cell) => el("td", {}, [cell])));
    return tr;
  });
  return el("div", { className: "responsive-table" }, [
    el("table", { className: "admin-table" }, [
      el("thead", {}, [el("tr", {}, headings.map((heading) => el("th", {}, [heading])))]),
      el("tbody", {}, bodyRows),
    ]),
  ]);
}

function panel(children) {
  return el("section", { className: "panel" }, children);
}

function panelHead(title) {
  return el("div", { className: "panel-head" }, [el("h2", {}, [title])]);
}

function pageHead(title, description) {
  return el("div", { className: "admin-page-head" }, [
    el("a", { className: "secondary-button", href: "#/" }, ["Back"]),
    el("div", {}, [el("h2", {}, [title]), el("p", {}, [description])]),
  ]);
}

function backLink() {
  return el("div", { className: "table-actions" }, [el("a", { className: "secondary-button", href: "#/" }, ["Back To Admin"])]);
}

function cellLink(label, href) {
  return el("a", { className: "table-link", href }, [label]);
}

function colorCell(color) {
  return el("span", { className: "color-chip" }, [
    el("span", { className: "swatch", style: `background: ${color}` }),
    color,
  ]);
}

function labeledInput(label, name, type, value, attrs = {}) {
  return labelWrap(label, el("input", { name, type, value, ...attrs }));
}

function colorPicker(label, name, value) {
  return labelWrap(label, el("input", { name, type: "color", value, "aria-label": label }));
}

function labelWrap(label, control) {
  return el("label", {}, [el("span", {}, [label]), control]);
}

function colorPresets(input) {
  const fieldset = el("fieldset", { className: "color-presets" }, [el("legend", {}, ["Default colors"])]);
  DEFAULT_COLORS.forEach((color) => {
    const button = el("button", {
      type: "button",
      className: "color-preset",
      style: `background: ${color}`,
      "aria-label": `Use color ${color}`,
      title: color,
      onclick: () => {
        input.value = color;
        updatePresetSelection(fieldset, color);
      },
    });
    button.dataset.color = color;
    fieldset.append(button);
  });
  input.addEventListener("input", () => updatePresetSelection(fieldset, input.value));
  updatePresetSelection(fieldset, input.value);
  return fieldset;
}

function updatePresetSelection(container, selected) {
  container.querySelectorAll(".color-preset").forEach((button) => {
    button.classList.toggle("selected", button.dataset.color === selected.toLowerCase());
  });
}

function syncText(text) {
  return el("p", { className: "sync" }, [text]);
}

function renderMissing(message) {
  setView(panel([pageHead("Not Found", message)]));
}

function setView(node) {
  els.view.replaceChildren(node);
}

function navigate(route) {
  const hash = route ? `#/${route}` : "#/";
  if (location.hash === hash) {
    renderRoute();
  } else {
    location.hash = hash;
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: adminHeaders(),
    ...options,
  });
  const body = await readJson(response);
  if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
  return body;
}

function adminToken() {
  return els.adminToken.value.trim();
}

function adminHeaders(extra = {}) {
  return {
    "Authorization": `Bearer ${adminToken()}`,
    ...extra,
  };
}

function pairingServerUrl() {
  const configured = state.appConfig?.server_url?.trim();
  if (!configured) {
    throw new Error("Set network.server_url in the Home Assistant app configuration before pairing.");
  }
  return configured;
}

function setStatus(message, isError = false) {
  els.status.textContent = message;
  els.status.classList.toggle("error", isError);
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function option(value, label) {
  return el("option", { value }, [label]);
}

function formatDateRange(competition) {
  return `${formatDate(competition.start_date)} to ${formatDate(competition.end_date)}`;
}

function formatDate(value) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function relativeTime(value) {
  const date = new Date(value);
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} hr ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function normalizeSlug(value) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (value === undefined || value === null || value === false) return;
    if (key === "className") node.className = value;
    else if (key === "style") node.setAttribute("style", value);
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  });
  children.forEach((child) => node.append(child instanceof Node ? child : document.createTextNode(String(child))));
  return node;
}
