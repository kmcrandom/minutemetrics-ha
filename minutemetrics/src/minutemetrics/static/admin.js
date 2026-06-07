const state = {
  appConfig: null,
  competitions: [],
  participants: [],
  memberships: [],
  selectedCompetitionId: sessionStorage.getItem("minutemetrics.selectedCompetitionId") || "",
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
  tokenForm: document.querySelector("#tokenForm"),
  adminToken: document.querySelector("#adminToken"),
  adminStatus: document.querySelector("#adminStatus"),
  workspace: document.querySelector("#adminWorkspace"),
  competitionForm: document.querySelector("#competitionForm"),
  competitionName: document.querySelector("#competitionName"),
  competitionSlug: document.querySelector("#competitionSlug"),
  competitionStartDate: document.querySelector("#competitionStartDate"),
  competitionEndDate: document.querySelector("#competitionEndDate"),
  competitions: document.querySelector("#competitions"),
  membershipPanel: document.querySelector("#membershipPanel"),
  membershipTitle: document.querySelector("#membershipTitle"),
  memberForm: document.querySelector("#memberForm"),
  existingParticipant: document.querySelector("#existingParticipant"),
  memberName: document.querySelector("#memberName"),
  memberColor: document.querySelector("#memberColor"),
  memberColorPresets: document.querySelector("#memberColorPresets"),
  members: document.querySelector("#competitionMembers"),
  participants: document.querySelector("#adminParticipants"),
  refreshAdmin: document.querySelector("#refreshAdmin"),
  clearData: document.querySelector("#clearData"),
  competitionTemplate: document.querySelector("#competitionTemplate"),
  participantTemplate: document.querySelector("#adminParticipantTemplate"),
  memberTemplate: document.querySelector("#memberTemplate"),
  pairingDialog: document.querySelector("#pairingDialog"),
  pairingTitle: document.querySelector("#pairingTitle"),
  qrFrame: document.querySelector("#qrFrame"),
  closePairing: document.querySelector("#closePairing"),
};

els.adminToken.value = sessionStorage.getItem("minutemetrics.adminToken") || "";
els.tokenForm.addEventListener("submit", (event) => unlock(event));
els.competitionForm.addEventListener("submit", (event) => createCompetition(event));
els.memberForm.addEventListener("submit", (event) => addMember(event));
els.existingParticipant.addEventListener("change", () => syncMemberInputs());
els.memberColor.addEventListener("input", () => updateColorPresetSelection());
els.refreshAdmin.addEventListener("click", () => loadAdminData());
els.clearData.addEventListener("click", () => clearSyncData());
els.closePairing.addEventListener("click", () => els.pairingDialog.close());

renderColorPresets();

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
    ensureSelectedCompetition();
    await loadMemberships();
    els.workspace.hidden = false;
    renderAll();
    setStatus(`Loaded ${competitions.length} competition${competitions.length === 1 ? "" : "s"}.`);
  } catch (error) {
    els.workspace.hidden = true;
    setStatus(error.message, true);
  }
}

async function loadMemberships() {
  if (!state.selectedCompetitionId) {
    state.memberships = [];
    return;
  }
  state.memberships = await fetchJson(`api/v1/admin/competitions/${state.selectedCompetitionId}/participants`);
}

function renderAll() {
  renderCompetitions();
  renderMemberForm();
  renderMembers();
  renderParticipants();
}

function ensureSelectedCompetition() {
  const selected = state.competitions.find((competition) => competition.id === state.selectedCompetitionId);
  if (selected) return;
  const fallback = state.competitions.find((competition) => competition.is_default) || state.competitions[0];
  state.selectedCompetitionId = fallback?.id || "";
  if (state.selectedCompetitionId) {
    sessionStorage.setItem("minutemetrics.selectedCompetitionId", state.selectedCompetitionId);
  }
}

async function createCompetition(event) {
  event.preventDefault();
  const name = els.competitionName.value.trim();
  const slug = normalizeSlug(els.competitionSlug.value.trim() || name);
  if (!name) return;

  setStatus(`Creating ${name}...`);
  try {
    const body = await fetchJson("api/v1/admin/competitions", {
      method: "POST",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        name,
        slug,
        start_date: els.competitionStartDate.value,
        end_date: els.competitionEndDate.value,
      }),
    });
    els.competitionForm.reset();
    state.selectedCompetitionId = body.id;
    sessionStorage.setItem("minutemetrics.selectedCompetitionId", body.id);
    await loadAdminData();
    setStatus(`Created ${body.name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderCompetitions() {
  els.competitions.replaceChildren();
  if (!state.competitions.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No competitions yet.";
    els.competitions.append(empty);
    return;
  }

  state.competitions.forEach((competition) => {
    const node = els.competitionTemplate.content.cloneNode(true);
    const article = node.querySelector(".admin-competition");
    const form = node.querySelector(".admin-competition-form");
    const name = node.querySelector(".admin-competition-name");
    const slug = node.querySelector(".admin-competition-slug");
    const start = node.querySelector(".admin-competition-start");
    const end = node.querySelector(".admin-competition-end");
    const meta = node.querySelector(".competition-meta");
    const manage = node.querySelector(".select-competition");
    const defaultButton = node.querySelector(".default-competition");
    const archive = node.querySelector(".archive-competition");

    article.classList.toggle("selected", competition.id === state.selectedCompetitionId);
    article.classList.toggle("archived", competition.status === "archived");
    name.value = competition.name;
    slug.value = competition.slug;
    start.value = competition.start_date;
    end.value = competition.end_date;
    meta.textContent = [
      `${competition.participant_count} participant${competition.participant_count === 1 ? "" : "s"}`,
      competition.is_default ? "default" : "",
      competition.status,
    ]
      .filter(Boolean)
      .join(" · ");
    manage.disabled = competition.id === state.selectedCompetitionId;
    defaultButton.disabled = competition.is_default;
    archive.textContent = competition.status === "archived" ? "Restore" : "Archive";

    form.addEventListener("submit", (event) => updateCompetition(event, competition, name, slug, start, end));
    manage.addEventListener("click", () => selectCompetition(competition.id));
    defaultButton.addEventListener("click", () => setDefaultCompetition(competition));
    archive.addEventListener("click", () => toggleArchiveCompetition(competition));
    els.competitions.append(node);
  });
}

async function updateCompetition(event, competition, nameInput, slugInput, startInput, endInput) {
  event.preventDefault();
  const name = nameInput.value.trim();
  const slug = normalizeSlug(slugInput.value.trim());
  if (!name || !slug) return;

  setStatus(`Saving ${competition.name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/competitions/${competition.id}`, {
      method: "PATCH",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        name,
        slug,
        start_date: startInput.value,
        end_date: endInput.value,
      }),
    });
    await loadAdminData();
    setStatus(`Saved ${body.name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function selectCompetition(competitionId) {
  state.selectedCompetitionId = competitionId;
  sessionStorage.setItem("minutemetrics.selectedCompetitionId", competitionId);
  setStatus("Loading competition participants...");
  try {
    await loadMemberships();
    renderAll();
    setStatus(`Managing ${selectedCompetition().name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function setDefaultCompetition(competition) {
  setStatus(`Setting ${competition.name} as default...`);
  try {
    await fetchJson(`api/v1/admin/competitions/${competition.id}/default`, {
      method: "POST",
      headers: adminHeaders(),
    });
    await loadAdminData();
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
    await fetchJson(`api/v1/admin/competitions/${competition.id}/${verb}`, {
      method: "POST",
      headers: adminHeaders(),
    });
    await loadAdminData();
    setStatus(`${competition.name} ${verb === "archive" ? "archived" : "restored"}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderMemberForm() {
  const competition = selectedCompetition();
  els.membershipPanel.hidden = !competition;
  if (!competition) return;

  els.membershipTitle.textContent = `${competition.name} Participants`;
  els.existingParticipant.replaceChildren(option("", "Create new participant"));
  state.participants
    .filter((participant) => !state.memberships.some((membership) => membership.participant_id === participant.id))
    .forEach((participant) => {
      els.existingParticipant.append(option(participant.id, participant.display_name));
    });
  syncMemberInputs();
}

function syncMemberInputs() {
  const participant = state.participants.find((item) => item.id === els.existingParticipant.value);
  if (participant) {
    els.memberName.value = participant.display_name;
    els.memberColor.value = participant.color;
    els.memberName.required = false;
  } else {
    els.memberName.required = true;
    if (!els.memberColor.value) els.memberColor.value = "#2f80ed";
  }
  updateColorPresetSelection();
}

async function addMember(event) {
  event.preventDefault();
  const competition = selectedCompetition();
  if (!competition) return;
  const participantId = els.existingParticipant.value || null;
  const displayName = els.memberName.value.trim();
  if (!participantId && !displayName) return;

  setStatus(`Adding participant to ${competition.name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/competitions/${competition.id}/participants`, {
      method: "POST",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(
        participantId
          ? { participant_id: participantId }
          : {
              display_name: displayName,
              color: els.memberColor.value,
            }
      ),
    });
    els.memberForm.reset();
    els.memberColor.value = DEFAULT_COLORS[0];
    updateColorPresetSelection();
    if (body.sync_token) {
      await showPairingQR(body.display_name, body.sync_token);
    }
    await loadAdminData();
    setStatus(`Added ${body.display_name} to ${competition.name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderMembers() {
  els.members.replaceChildren();
  const competition = selectedCompetition();
  if (!competition) return;
  if (!state.memberships.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No participants in this competition yet.";
    els.members.append(empty);
    return;
  }

  state.memberships.forEach((membership) => {
    const node = els.memberTemplate.content.cloneNode(true);
    const form = node.querySelector(".member-form");
    const swatch = node.querySelector(".swatch");
    const name = node.querySelector(".member-name");
    const color = node.querySelector(".member-color");
    const active = node.querySelector(".member-active");
    const sync = node.querySelector(".sync");

    swatch.style.background = membership.color;
    name.value = membership.display_name_override || "";
    name.placeholder = membership.participant_display_name;
    color.value = membership.color_override || membership.participant_color;
    active.checked = membership.active;
    sync.textContent = membership.last_synced_at
      ? `${membership.participant_display_name} synced ${relativeTime(membership.last_synced_at)}`
      : `${membership.participant_display_name} has not synced yet`;

    form.addEventListener("submit", (event) => updateMember(event, membership, name, color, active));
    node.querySelector(".remove-member").addEventListener("click", () => removeMember(membership));
    els.members.append(node);
  });
}

async function updateMember(event, membership, nameInput, colorInput, activeInput) {
  event.preventDefault();
  const competition = selectedCompetition();
  if (!competition) return;
  setStatus(`Saving ${membership.display_name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/competitions/${competition.id}/participants/${membership.participant_id}`, {
      method: "PATCH",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        display_name_override: nameInput.value.trim() || null,
        color_override: colorInput.value || null,
        active: activeInput.checked,
      }),
    });
    await loadAdminData();
    setStatus(`Saved ${body.display_name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function removeMember(membership) {
  const competition = selectedCompetition();
  if (!competition) return;
  if (!confirm(`Remove ${membership.display_name} from ${competition.name}? Their synced Health data will remain.`)) return;
  setStatus(`Removing ${membership.display_name}...`);
  try {
    await fetchJson(`api/v1/admin/competitions/${competition.id}/participants/${membership.participant_id}`, {
      method: "DELETE",
      headers: adminHeaders(),
    });
    await loadAdminData();
    setStatus(`Removed ${membership.display_name} from ${competition.name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderParticipants() {
  els.participants.replaceChildren();
  if (!state.participants.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No participants yet.";
    els.participants.append(empty);
    return;
  }

  state.participants.forEach((participant) => {
    const node = els.participantTemplate.content.cloneNode(true);
    const article = node.querySelector(".admin-participant");
    const form = node.querySelector(".admin-participant-form");
    const swatch = node.querySelector(".swatch");
    const name = node.querySelector(".admin-participant-name");
    const color = node.querySelector(".admin-participant-color");
    const sync = node.querySelector(".sync");

    swatch.style.background = participant.color;
    name.value = participant.display_name;
    color.value = participant.color;
    sync.textContent = participant.last_synced_at
      ? `Last synced ${relativeTime(participant.last_synced_at)}`
      : "No sync yet";

    form.addEventListener("submit", (event) => updateParticipant(event, participant, name, color));
    node.querySelector(".pair-participant").addEventListener("click", () => rotateAndShowPairingQR(participant));
    node.querySelector(".delete-participant").addEventListener("click", () => deleteParticipant(participant));

    article.dataset.participantId = participant.id;
    els.participants.append(node);
  });
}

async function updateParticipant(event, participant, nameInput, colorInput) {
  event.preventDefault();
  const displayName = nameInput.value.trim();
  if (!displayName) return;

  setStatus(`Saving ${participant.display_name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/participants/${participant.id}`, {
      method: "PATCH",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        display_name: displayName,
        color: colorInput.value,
      }),
    });
    await loadAdminData();
    setStatus(`Saved ${body.display_name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function rotateAndShowPairingQR(participant) {
  if (!confirm(`Create a new pairing code for ${participant.display_name}? The previous iPhone sync token will stop working.`)) {
    return;
  }
  setStatus(`Creating pairing code for ${participant.display_name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/participants/${participant.id}/rotate-token`, {
      method: "POST",
      headers: adminHeaders(),
    });
    await showPairingQR(participant.display_name, body.sync_token);
    setStatus(`Pairing code ready for ${participant.display_name}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function deleteParticipant(participant) {
  if (!confirm(`Delete ${participant.display_name} and all of their synced data?`)) {
    return;
  }
  setStatus(`Deleting ${participant.display_name}...`);
  try {
    const body = await fetchJson(`api/v1/admin/participants/${participant.id}`, {
      method: "DELETE",
      headers: adminHeaders(),
    });
    await loadAdminData();
    setStatus(`Deleted ${participant.display_name}.`);
    return body;
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function clearSyncData() {
  if (!confirm("Clear all synced exercise data and sync history? Participants and pairing tokens will remain.")) {
    return;
  }
  setStatus("Clearing sync data...");
  try {
    const body = await fetchJson("api/v1/admin/data", {
      method: "DELETE",
      headers: adminHeaders(),
    });
    await loadAdminData();
    setStatus(`Cleared ${body.deleted_exercise_days} exercise day${body.deleted_exercise_days === 1 ? "" : "s"}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
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

function selectedCompetition() {
  return state.competitions.find((competition) => competition.id === state.selectedCompetitionId) || null;
}

function renderColorPresets() {
  els.memberColorPresets.replaceChildren();
  const legend = document.createElement("legend");
  legend.textContent = "Default colors";
  els.memberColorPresets.append(legend);

  DEFAULT_COLORS.forEach((color) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "color-preset";
    button.style.background = color;
    button.dataset.color = color;
    button.title = color;
    button.setAttribute("aria-label", `Use color ${color}`);
    button.addEventListener("click", () => {
      els.memberColor.value = color;
      updateColorPresetSelection();
    });
    els.memberColorPresets.append(button);
  });
  updateColorPresetSelection();
}

function updateColorPresetSelection() {
  const selected = els.memberColor.value.toLowerCase();
  els.memberColorPresets.querySelectorAll(".color-preset").forEach((button) => {
    button.classList.toggle("selected", button.dataset.color === selected);
  });
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
  els.adminStatus.textContent = message;
  els.adminStatus.classList.toggle("error", isError);
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function option(value, label) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label;
  return item;
}

function normalizeSlug(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-+/g, "-");
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
  for (const [unit, seconds] of units) {
    const amount = Math.round(diffSeconds / seconds);
    if (Math.abs(amount) >= 1) {
      return new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(amount, unit);
    }
  }
  return "just now";
}
