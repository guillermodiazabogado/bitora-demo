"use strict";

const $ = (selector) => document.querySelector(selector);
const state = { scope: null, leads: [], loading: false, csrfToken: "" };

function cleanPositive(value, label) {
  const number = Number(value);
  if (!Number.isInteger(number) || number <= 0) throw new Error(`${label} debe ser un entero positivo.`);
  return number;
}

function scopeFromForm() {
  return {
    organizationId: cleanPositive($("#organizationId").value, "Organización"),
    eventId: cleanPositive($("#eventId").value, "Evento"),
    companyId: cleanPositive($("#companyId").value, "Empresa"),
  };
}

function applyQueryScope() {
  const query = new URLSearchParams(location.search);
  $("#organizationId").value = query.get("organization_id") || "";
  $("#eventId").value = query.get("event_id") || "";
  $("#companyId").value = query.get("company_id") || "";
}

function route(suffix = "") {
  const { organizationId, eventId } = state.scope;
  return `/api/v5/organizations/${organizationId}/events/${eventId}${suffix}`;
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.csrfToken && String(options.method || "GET").toUpperCase() !== "GET") headers["X-CSRF-Token"] = state.csrfToken;
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  const type = response.headers.get("content-type") || "";
  const data = type.includes("application/json") ? await response.json() : { error: await response.text() };
  if (!response.ok) {
    const error = new Error(data.error || `Solicitud rechazada (${response.status})`);
    error.code = data.code || "REQUEST_FAILED";
    throw error;
  }
  return data;
}

async function loadSession() {
  const response = await fetch("/api/auth/me", { credentials: "same-origin" });
  const auth = await response.json();
  if (!response.ok || !auth.authenticated) {
    location.href = "/login.html";
    throw new Error("Sesión requerida.");
  }
  state.csrfToken = auth.csrf_token || "";
}

function setStatus(message = "", kind = "") {
  const node = $("#status");
  node.textContent = message;
  node.className = `status ${kind}`.trim();
}

function newIdempotency(prefix) {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `lead-${prefix}-${random}`;
}

function renewCaptureKey() {
  $("#captureIdempotency").value = newIdempotency("capture");
}

function safeSnapshot(lead) {
  try { return typeof lead.data_snapshot_json === "string" ? JSON.parse(lead.data_snapshot_json || "{}") : (lead.data_snapshot_json || {}); }
  catch { return {}; }
}

function formatDate(value) {
  if (!value) return "Sin fecha";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
}

function renderLeads() {
  const body = $("#leadsTable tbody");
  body.replaceChildren();
  $("#leadCount").textContent = String(state.leads.length);
  $("#leadsEmpty").classList.toggle("hidden", state.loading || state.leads.length > 0);
  $("#leadsTable").classList.toggle("hidden", state.loading || state.leads.length === 0);
  state.leads.forEach((lead) => {
    const snapshot = safeSnapshot(lead);
    const row = document.createElement("tr");
    const cells = [
      [`${snapshot.first_name || ""} ${snapshot.last_name || ""}`.trim() || `Lead #${lead.id}`, snapshot.company || "Empresa no informada"],
      [snapshot.email || snapshot.phone || "No compartido", snapshot.position || "Campos según consentimiento"],
      [lead.qualification || "UNQUALIFIED", ""],
      [lead.follow_up_status || "NEW", ""],
      [formatDate(lead.captured_at), `Stand ${lead.stand_id || "—"}`],
    ];
    cells.forEach(([primary, secondary]) => {
      const cell = document.createElement("td");
      const strong = document.createElement("strong");
      strong.textContent = primary;
      cell.append(strong);
      if (secondary) { const span = document.createElement("span"); span.textContent = secondary; cell.append(span); }
      row.append(cell);
    });
    body.append(row);
  });
}

async function loadLeads() {
  if (!state.scope || state.loading) return;
  state.loading = true;
  $("#leadsLoading").classList.remove("hidden");
  $("#leadsError").classList.add("hidden");
  renderLeads();
  try {
    const result = await api(route(`/companies/${state.scope.companyId}/leads`));
    state.leads = Array.isArray(result.items) ? result.items : [];
  } catch (error) {
    state.leads = [];
    $("#leadsError").textContent = `${error.code || "ERROR"}: ${error.message}`;
    $("#leadsError").classList.remove("hidden");
  } finally {
    state.loading = false;
    $("#leadsLoading").classList.add("hidden");
    renderLeads();
  }
}

async function applyScope(event) {
  event?.preventDefault();
  try {
    state.scope = scopeFromForm();
    const query = new URLSearchParams({ organization_id: state.scope.organizationId, event_id: state.scope.eventId, company_id: state.scope.companyId });
    history.replaceState(null, "", `${location.pathname}?${query}`);
    setStatus("Alcance aplicado. Cargando datos reales…", "loading");
    await loadLeads();
    setStatus("Alcance operativo cargado.", "success");
  } catch (error) { setStatus(error.message, "error"); }
}

async function captureLead(event) {
  event.preventDefault();
  if (!state.scope) return setStatus("Aplicá primero el alcance operativo.", "error");
  const button = $("#captureButton");
  button.disabled = true;
  setStatus("Registrando captura…", "loading");
  try {
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    ["consent_id", "stand_id", "device_id"].forEach((key) => { values[key] = values[key] ? Number(values[key]) : null; });
    values.company_id = state.scope.companyId;
    values.source = "QR_SCAN";
    const result = await api(route("/leads/captures"), { method: "POST", body: JSON.stringify(values) });
    if (!result.ok) throw new Error(result.reason_code || "La captura fue rechazada.");
    setStatus(result.duplicate ? "La captura ya había sido registrada; no se duplicó." : "Lead capturado correctamente.", "success");
    event.currentTarget.reset();
    renewCaptureKey();
    await loadLeads();
  } catch (error) { setStatus(`${error.code || "ERROR"}: ${error.message}`, "error"); }
  finally { button.disabled = false; }
}

async function exportLeads(event) {
  event.preventDefault();
  if (!state.scope) return setStatus("Aplicá primero el alcance operativo.", "error");
  const fields = [...event.currentTarget.querySelectorAll('input[name="fields"]:checked')].map((input) => input.value);
  if (!fields.length) return setStatus("Seleccioná al menos un campo para exportar.", "error");
  const button = $("#exportButton");
  button.disabled = true;
  setStatus("Generando exportación auditada…", "loading");
  try {
    const result = await api(route(`/companies/${state.scope.companyId}/leads/export`), { method: "POST", body: JSON.stringify({ fields, idempotency_key: newIdempotency("export") }) });
    const blob = new Blob([result.csv || ""], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `bitora-leads-event-${state.scope.eventId}-company-${state.scope.companyId}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
    setStatus(`Exportación lista: ${Number(result.count || 0)} leads.`, "success");
  } catch (error) { setStatus(`${error.code || "ERROR"}: ${error.message}`, "error"); }
  finally { button.disabled = false; }
}

$("#scopeForm").addEventListener("submit", applyScope);
$("#captureForm").addEventListener("submit", captureLead);
$("#exportForm").addEventListener("submit", exportLeads);
$("#reloadButton").addEventListener("click", () => loadLeads());
$("#renewKeyButton").addEventListener("click", renewCaptureKey);

async function start() {
  await loadSession();
  applyQueryScope();
  renewCaptureKey();
  if ($("#organizationId").value && $("#eventId").value && $("#companyId").value) await applyScope();
}

start().catch((error) => setStatus(error.message, "error"));
