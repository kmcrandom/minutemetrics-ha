const state = {
  appConfig: null,
  participants: [],
};

const els = {
  tokenForm: document.querySelector("#tokenForm"),
  adminToken: document.querySelector("#adminToken"),
  adminStatus: document.querySelector("#adminStatus"),
  workspace: document.querySelector("#adminWorkspace"),
  participantForm: document.querySelector("#participantForm"),
  participantName: document.querySelector("#participantName"),
  participantColor: document.querySelector("#participantColor"),
  serverUrl: document.querySelector("#serverUrl"),
  participants: document.querySelector("#adminParticipants"),
  refreshParticipants: document.querySelector("#refreshParticipants"),
  clearData: document.querySelector("#clearData"),
  template: document.querySelector("#adminParticipantTemplate"),
  pairingDialog: document.querySelector("#pairingDialog"),
  pairingTitle: document.querySelector("#pairingTitle"),
  qrFrame: document.querySelector("#qrFrame"),
  closePairing: document.querySelector("#closePairing"),
};

els.adminToken.value = sessionStorage.getItem("minutemetrics.adminToken") || "";
els.tokenForm.addEventListener("submit", (event) => unlock(event));
els.participantForm.addEventListener("submit", (event) => createParticipant(event));
els.refreshParticipants.addEventListener("click", () => loadParticipants());
els.clearData.addEventListener("click", () => clearSyncData());
els.closePairing.addEventListener("click", () => els.pairingDialog.close());

loadAppConfig().then(() => {
  if (els.adminToken.value.trim()) {
    loadParticipants();
  }
});

async function loadAppConfig() {
  const response = await fetch("api/v1/app-config", { cache: "no-store" });
  if (response.ok) {
    state.appConfig = await response.json();
  }
  els.serverUrl.value = pairingServerUrl();
}

async function unlock(event) {
  event.preventDefault();
  await loadParticipants();
}

async function loadParticipants() {
  const token = adminToken();
  if (!token) return;
  setStatus("Loading participants...");
  try {
    const response = await fetch("api/v1/admin/participants", {
      cache: "no-store",
      headers: adminHeaders(),
    });
    const body = await readJson(response);
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    sessionStorage.setItem("minutemetrics.adminToken", token);
    state.participants = body;
    els.workspace.hidden = false;
    renderParticipants();
    setStatus(`Loaded ${body.length} participant${body.length === 1 ? "" : "s"}.`);
  } catch (error) {
    els.workspace.hidden = true;
    setStatus(error.message, true);
  }
}

async function createParticipant(event) {
  event.preventDefault();
  const displayName = els.participantName.value.trim();
  if (!displayName) return;

  setStatus("Creating participant...");
  try {
    const response = await fetch("api/v1/admin/participants", {
      method: "POST",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        display_name: displayName,
        color: els.participantColor.value,
      }),
    });
    const body = await readJson(response);
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);

    els.participantName.value = "";
    await showPairingQR(body.display_name, body.sync_token);
    await loadParticipants();
    setStatus(`Created ${body.display_name}.`);
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
    const node = els.template.content.cloneNode(true);
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
    const response = await fetch(`api/v1/admin/participants/${participant.id}`, {
      method: "PATCH",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        display_name: displayName,
        color: colorInput.value,
      }),
    });
    const body = await readJson(response);
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    await loadParticipants();
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
    const response = await fetch(`api/v1/admin/participants/${participant.id}/rotate-token`, {
      method: "POST",
      headers: adminHeaders(),
    });
    const body = await readJson(response);
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
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
    const response = await fetch(`api/v1/admin/participants/${participant.id}`, {
      method: "DELETE",
      headers: adminHeaders(),
    });
    const body = await readJson(response);
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    await loadParticipants();
    setStatus(`Deleted ${participant.display_name}.`);
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
    const response = await fetch("api/v1/admin/data", {
      method: "DELETE",
      headers: adminHeaders(),
    });
    const body = await readJson(response);
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    await loadParticipants();
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
  return configured || window.location.origin;
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
