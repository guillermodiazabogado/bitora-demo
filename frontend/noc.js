const params = new URLSearchParams(location.search);
const eventId = Number(params.get("event_id") || 0);
const refreshSeconds = Math.max(5, Number(params.get("refresh") || 10));
const $ = (selector) => document.querySelector(selector);

async function get(path) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" } });
  if (response.status === 401) {
    location.href = "/login.html";
    throw new Error("Sesion requerida");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Error");
  return data;
}

function statusRows(services) {
  return Object.entries(services).map(([key, value]) => `<span class="noc-status ${value.status}"><i></i>${key} · ${value.label}</span>`).join("");
}

function bars(rows) {
  return rows.map((row) => `<div class="noc-room"><b>${row.room}</b><strong>${row.percentage}%</strong><div><i class="${row.color}" style="width:${row.percentage}%"></i></div><small>${row.present} presentes / ${row.capacity}</small></div>`).join("");
}

function sparkline(rows) {
  if (!rows.length) return `<span class="noc-empty">Sin datos recientes</span>`;
  const max = Math.max(...rows.map((row) => Number(row.value || 0)), 1);
  return rows.map((row) => `<i title="${row.label}: ${row.value}" style="height:${Math.max(8, Number(row.value || 0) / max * 100)}%"></i>`).join("");
}

async function load() {
  try {
    const [visual, engine, diagnostics, communications] = await Promise.all([
      get(`/api/reports/visual-summary?event_id=${eventId}`),
      get(`/api/data-visualization?event_id=${eventId}&dashboard=operational&period=today`),
      get("/api/diagnostics/status"),
      get(`/api/communications?event_id=${eventId}`),
    ]);
    $("#nocEvent").textContent = visual.event.name;
    $("#nocStatus").textContent = `${engine.vertical?.name || "Conference"} · ${diagnostics.app_status.toUpperCase()} · actualiza cada ${refreshSeconds}s`;
    $("#nocGeneral").innerHTML = `<strong class="noc-health ${diagnostics.app_status}">${visual.event_health}%</strong><span>${visual.event.venue || "Evento activo"}</span><small>${diagnostics.event_health.active_events} evento(s) activo(s)</small>`;
    $("#nocAccess").innerHTML = `<div class="noc-kpis"><b>${diagnostics.metrics.qr_per_minute}<small>QR/min</small></b><b>${diagnostics.metrics.accesses_per_minute}<small>Accesos/min</small></b><b>${diagnostics.metrics.p95_response_ms}<small>p95 ms</small></b></div>`;
    const totals = visual.totals;
    $("#nocAccreditations").innerHTML = `<div class="noc-kpis"><b>${totals.registered || 0}<small>Inscriptos</small></b><b>${totals.checked || 0}<small>Acreditados</small></b><b>${Math.max(0, Number(totals.registered || 0) - Number(totals.checked || 0) - Number(totals.cancelled || 0))}<small>Pendientes</small></b><b>${totals.cancelled || 0}<small>Cancelados</small></b></div>`;
    const engineRooms = (engine.heatmaps?.rooms || []).map((row) => ({
      room: row.label,
      percentage: Number(row.percentage || 0),
      present: Number(row.value || 0),
      capacity: Number(row.capacity || 0),
      color: Number(row.percentage || 0) > 60 ? "green" : Number(row.percentage || 0) >= 30 ? "yellow" : "red",
    }));
    $("#nocRooms").innerHTML = bars(engineRooms.length ? engineRooms : (visual.occupancy_by_room || []));
    const alerts = [...(engine.predictive_alerts || []), ...(visual.operational_alerts || []), ...(diagnostics.alerts || [])];
    $("#nocAlerts").innerHTML = `<strong class="noc-alert-count ${alerts.length ? "warning" : "healthy"}">${alerts.length}</strong><span>${alerts.length ? "Requieren atencion" : "Sin alertas activas"}</span>`;
    $("#nocRejections").innerHTML = (visual.rejection_reasons || []).map((row) => `<div class="noc-list-row"><span>${row.label || "Otro"}</span><b>${row.value}</b></div>`).join("") || `<span class="noc-empty">Sin rechazos</span>`;
    $("#nocFlow").innerHTML = sparkline(engine.series?.accesses || visual.access_by_time || []);
    $("#nocTerminals").innerHTML = `<div class="noc-kpis"><b>${diagnostics.event_health.active_terminals}<small>Terminales</small></b><b>${diagnostics.event_health.active_operators}<small>Operadores</small></b><b>${diagnostics.event_health.inactive_terminals}<small>Inactivas</small></b></div>`;
    const queue = communications.queue_metrics || {};
    $("#nocCommunications").innerHTML = `<div class="noc-kpis"><b>${queue.emails_sent || 0}<small>Enviados</small></b><b>${queue.pending || 0}<small>Pendientes</small></b><b>${queue.errors || 0}<small>Errores</small></b></div>`;
    $("#nocInfrastructure").innerHTML = statusRows(diagnostics.services);
  } catch (error) {
    $("#nocStatus").textContent = error.message;
  }
}

setInterval(() => { $("#nocClock").textContent = new Date().toLocaleTimeString("es-AR"); }, 1000);
load();
setInterval(load, refreshSeconds * 1000);
