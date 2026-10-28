"use strict";
const $ = (selector) => document.querySelector(selector);
const state = { csrfToken: "", scope: null, loading: false };

function positive(value, label) { const number = Number(value); if (!Number.isInteger(number) || number <= 0) throw new Error(`${label} debe ser un entero positivo.`); return number; }
function optionalPositive(value, label) { return value ? positive(value, label) : null; }
function setStatus(message, kind = "") { const node = $("#status"); node.textContent = message || ""; node.className = `status ${kind}`.trim(); }
function newKey() { const random = crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`; $("#idempotencyKey").value = `vehicle-access-${random}`; }
function route(suffix) { return `/api/v5/organizations/${state.scope.organizationId}/events/${state.scope.eventId}/vehicles${suffix}`; }

async function api(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (method !== "GET") {
    if (!state.csrfToken) throw new Error("CSRF no disponible. Volvé a iniciar sesión.");
    headers["X-CSRF-Token"] = state.csrfToken;
  }
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) { const error = new Error(data.error || `Solicitud rechazada (${response.status})`); error.code = data.code || "REQUEST_FAILED"; throw error; }
  return data;
}

async function initializeAuth() {
  const response = await fetch("/api/auth/me", { credentials: "same-origin" });
  const auth = await response.json().catch(() => ({}));
  if (!response.ok || !auth.authenticated || !auth.csrf_token) throw new Error("Sesión autenticada y CSRF son obligatorios para operar vehículos.");
  state.csrfToken = auth.csrf_token;
  ["#scopeButton", "#reloadButton", "#accessButton", "#renewKeyButton"].forEach((selector) => { $(selector).disabled = false; });
  setStatus("Sesión validada. Aplicá el alcance operativo.", "success");
}

function applyQuery() { const query = new URLSearchParams(location.search); $("#organizationId").value = query.get("organization_id") || ""; $("#eventId").value = query.get("event_id") || ""; }
function renderMetrics(metrics) { ["expected", "inside", "entries", "exits", "rejected"].forEach((key) => { $(`[data-metric="${key}"]`).textContent = String(Number(metrics[key] || 0)); }); const empty = ["expected", "inside", "entries", "exits", "rejected"].every((key) => Number(metrics[key] || 0) === 0); $("#dashboardEmpty").classList.toggle("hidden", !empty); $("#metrics").classList.toggle("hidden", empty); }

async function loadDashboard() {
  if (!state.scope || state.loading) return;
  state.loading = true; $("#dashboardLoading").classList.remove("hidden"); $("#dashboardError").classList.add("hidden"); $("#dashboardEmpty").classList.add("hidden");
  try { const result = await api(route("/dashboard")); renderMetrics(result.metrics || {}); }
  catch (error) { $("#metrics").classList.add("hidden"); $("#dashboardError").textContent = `${error.code || "ERROR"}: ${error.message}`; $("#dashboardError").classList.remove("hidden"); }
  finally { state.loading = false; $("#dashboardLoading").classList.add("hidden"); }
}

async function applyScope(event) {
  event?.preventDefault();
  try { state.scope = { organizationId: positive($("#organizationId").value, "Organización"), eventId: positive($("#eventId").value, "Evento") }; const query = new URLSearchParams({ organization_id: state.scope.organizationId, event_id: state.scope.eventId }); history.replaceState(null, "", `${location.pathname}?${query}`); setStatus("Cargando operación del evento…", "loading"); await loadDashboard(); setStatus("Alcance operativo cargado.", "success"); }
  catch (error) { setStatus(error.message, "error"); }
}

function decisionMessage(reason, direction) {
  const messages = {
    ANTI_PASSBACK: "Ingreso rechazado: el vehículo ya figura dentro del predio. Registrá primero su egreso.",
    NO_ACTIVE_SLOT: "Movimiento rechazado: el vehículo no tiene un slot activo para este gate o destino.",
    ENTRY_LIMIT_REACHED: "Ingreso rechazado: el slot alcanzó su límite de entradas.",
    OUTSIDE_TIME_WINDOW: "Movimiento rechazado: el slot todavía no está vigente.",
    SLOT_EXPIRED: "Movimiento rechazado: el slot está vencido.",
    WRONG_GATE: "Movimiento rechazado: el gate no coincide con el slot autorizado.",
    WRONG_DESTINATION: "Movimiento rechazado: el destino no coincide con el slot autorizado.",
    RULE_DENIED: direction === "EXIT" ? "Egreso rechazado: el vehículo no figura dentro del predio." : "Movimiento rechazado por regla operativa.",
  };
  return messages[reason] || `Movimiento rechazado: ${reason || "sin motivo informado"}.`;
}

async function recordAccess(event) {
  event.preventDefault(); if (!state.scope) return setStatus("Aplicá primero el alcance operativo.", "error");
  const form = event.currentTarget; const button = $("#accessButton"); const resultNode = $("#accessResult"); button.disabled = true; resultNode.className = "access-result hidden"; setStatus("Registrando movimiento…", "loading");
  try {
    const values = Object.fromEntries(new FormData(form).entries()); values.plate = String(values.plate || "").toUpperCase().replace(/[^A-Z0-9]/g, ""); if (!values.plate) throw new Error("Ingresá una patente válida.");
    values.gate_id = optionalPositive(values.gate_id, "Gate"); values.destination_id = optionalPositive(values.destination_id, "Destino"); values.driver_entity_id = optionalPositive(values.driver_entity_id, "Conductor"); values.device_id = optionalPositive(values.device_id, "Dispositivo");
    const result = await api(route("/access"), { method: "POST", body: JSON.stringify(values) }); const reason = result.decision?.reason_code || result.event?.reason_code; const allowed = result.ok || result.event?.decision === "ALLOW";
    resultNode.textContent = result.duplicate ? "La operación ya estaba registrada; no se duplicó." : allowed ? `${values.direction === "ENTRY" ? "Ingreso" : "Egreso"} registrado correctamente para ${values.plate}.` : decisionMessage(reason, values.direction);
    resultNode.className = `access-result ${allowed ? "success" : reason === "ANTI_PASSBACK" || reason === "NO_ACTIVE_SLOT" ? "warning" : "error"}`; setStatus(allowed ? "Estado vehicular actualizado." : "El servidor registró un movimiento rechazado.", allowed ? "success" : "warning"); newKey(); if (allowed) { $("#plate").value = ""; } await loadDashboard();
  } catch (error) { resultNode.textContent = `${error.code || "ERROR"}: ${error.message}`; resultNode.className = "access-result error"; setStatus("No se pudo registrar el movimiento.", "error"); }
  finally { button.disabled = false; }
}

$("#scopeForm").addEventListener("submit", applyScope); $("#accessForm").addEventListener("submit", recordAccess); $("#reloadButton").addEventListener("click", loadDashboard); $("#renewKeyButton").addEventListener("click", newKey); applyQuery(); newKey(); initializeAuth().then(() => { if ($("#organizationId").value && $("#eventId").value) applyScope(); }).catch((error) => setStatus(error.message, "error"));
