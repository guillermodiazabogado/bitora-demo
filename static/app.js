const state = {
  events: [],
  types: [],
  spaces: [],
  activities: [],
  bags: [],
  displayConfig: null,
  accreditations: [],
  reservations: [],
  alerts: [],
  systemStatus: null,
  summary: null,
  attendanceDashboard: null,
  marketingDashboard: null,
  readiness: null,
  networkInfo: null,
  authUser: null,
  users: [],
  audit: [],
  communications: null,
  diagnostics: null,
  simulator: null,
  visualization: null,
  visualizationLayouts: [],
  demoReal: null,
  currentUser: "Admin",
  eventId: null,
  cameraStream: null,
  scanning: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setHref(selector, href) {
  const node = $(selector);
  if (node) node.href = href;
}

function applyAppConfig(config) {
  if (!config?.demo || document.querySelector(".demo-ribbon")) return;
  const ribbon = document.createElement("div");
  ribbon.className = "demo-ribbon";
  ribbon.textContent = "BITORA DEMO";
  document.body.appendChild(ribbon);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (response.status === 401) {
    location.href = "/login.html";
    throw new Error("Sesion requerida");
  }
  if (!response.ok) throw new Error(data.error || "Error inesperado");
  return data;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function setView(name) {
  if (name === "visualization") name = "reports";
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  $$("nav button").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
}

function organizeReportAndDiagnosticViews() {
  const analytics = $("#visualization");
  const slot = $("#reportsAnalyticsSlot");
  if (analytics && slot && analytics.parentElement !== slot) {
    slot.appendChild(analytics);
    analytics.classList.remove("hidden");
  }
}

async function loadEvents() {
  await loadAuth();
  await loadUsers();
  const previousEventId = state.eventId;
  state.events = await api("/api/events");
  const select = $("#eventSelect");
  select.innerHTML = state.events.map((event) => `<option value="${event.id}">${event.name}</option>`).join("");
  if (previousEventId && state.events.some((event) => Number(event.id) === Number(previousEventId))) {
    select.value = String(previousEventId);
  }
  if ($("#cloneEventSelect")) {
    $("#cloneEventSelect").innerHTML = state.events.map((event) => `<option value="${event.id}">${event.name}</option>`).join("");
  }
  state.eventId = Number(select.value || state.events[0]?.id || 0);
  updateMetrics();
  await Promise.all([loadTypes(), loadAccreditations(), loadAgenda(), loadAlerts(), loadSystemStatus(), loadNetworkInfo(), loadSummary(), loadMarketing(), loadReadiness(), loadAudit(), loadCommunications(), loadDemoReal(), loadLogs()]);
}

async function loadAuth() {
  const auth = await api("/api/auth/me");
  applyAppConfig(auth.config);
  state.authUser = auth.user || null;
  if (state.authUser) {
    state.currentUser = state.authUser.name;
    $("#logoutBtn").classList.remove("hidden");
    $("#diagnosticsNav")?.classList.toggle("hidden", state.authUser.role !== "Super Admin");
    $("#simulatorNav")?.classList.toggle("hidden", state.authUser.role !== "Super Admin");
    $("#visualization")?.classList.toggle(
      "hidden",
      !["Super Admin", "Productor", "Coordinador"].includes(state.authUser.role),
    );
  } else {
    $("#logoutBtn").classList.add("hidden");
    $("#diagnosticsNav")?.classList.add("hidden");
    $("#simulatorNav")?.classList.add("hidden");
    $("#visualization")?.classList.add("hidden");
  }
}

function formatDuration(seconds) {
  const value = Number(seconds || 0);
  const days = Math.floor(value / 86400);
  const hours = Math.floor((value % 86400) / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  return `${days ? `${days}d ` : ""}${hours}h ${minutes}m`;
}

function renderDiagnosticsLogs() {
  const filter = $("#diagnosticsLogFilter")?.value || "";
  const logs = (state.diagnostics?.logs || []).filter((row) => !filter || row.level === filter);
  $("#diagnosticsLogs").innerHTML = logs.map((row) => `
    <article class="audit-row diagnostics-log ${row.level}">
      <strong>${row.level.toUpperCase()} · ${row.module}</strong>
      <span>${row.message}</span>
      <small>${row.created_at}${row.detail ? ` · ${row.detail}` : ""}</small>
    </article>
  `).join("") || `<p class="empty">Sin logs para este filtro.</p>`;
}

async function loadDiagnostics() {
  if (state.authUser?.role !== "Super Admin") {
    $("#diagnosticsAccessDenied")?.classList.remove("hidden");
    $("#diagnosticsContent")?.classList.add("hidden");
    return;
  }
  $("#diagnosticsAccessDenied")?.classList.add("hidden");
  $("#diagnosticsContent")?.classList.remove("hidden");
  state.diagnostics = await api("/api/diagnostics/status");
  const data = state.diagnostics;
  const labels = { healthy: "Normal", warning: "Atencion", critical: "Critico" };
  $("#diagnosticsTrafficLight").className = `diagnostics-light ${data.app_status}`;
  $("#diagnosticsStatusText").textContent = labels[data.app_status] || data.app_status;
  $("#diagnosticsMeta").textContent = `${data.meta.version} · ${data.meta.env} · ${new Date(data.meta.generated_at).toLocaleString()}`;
  $("#diagnosticsServices").innerHTML = Object.entries(data.services).map(([key, item]) => `
    <article class="diagnostics-service ${item.status}">
      <span class="status-dot"></span>
      <div><strong>${key.replace("_", " ")}</strong><small>${item.label}</small></div>
    </article>
  `).join("");
  const metrics = data.metrics;
  $("#diagnosticsMetrics").innerHTML = `
    <div><strong>${formatDuration(metrics.uptime_seconds)}</strong><span>Uptime</span></div>
    <div><strong>${metrics.average_response_ms} ms</strong><span>Respuesta promedio</span></div>
    <div><strong>${metrics.p95_response_ms} ms</strong><span>p95</span></div>
    <div><strong>${metrics.p99_response_ms} ms</strong><span>p99</span></div>
    <div><strong>${metrics.requests_per_minute}</strong><span>Consultas/min</span></div>
    <div><strong>${metrics.concurrent_users}</strong><span>Usuarios concurrentes</span></div>
    <div><strong>${metrics.active_operators}</strong><span>Operadores activos</span></div>
    <div><strong>${metrics.qr_per_minute}</strong><span>QR/min</span></div>
    <div><strong>${metrics.accesses_per_minute}</strong><span>Accesos/min</span></div>
  `;
  const database = data.database;
  $("#diagnosticsDatabase").innerHTML = `
    <div><span>Motor activo</span><strong>${database.engine}</strong></div>
    <div><span>Tamano</span><strong>${formatBytes(database.size_bytes)}</strong></div>
    <div><span>Conexiones activas</span><strong>${database.active_connections}</strong></div>
    <div><span>Consultas lentas</span><strong>${database.slow_queries}</strong></div>
    <div><span>Ultima migracion</span><strong>${database.last_migration}</strong></div>
    <div><span>Cache</span><strong>${data.cache.backend}</strong></div>
  `;
  const queues = data.queues;
  $("#diagnosticsQueues").innerHTML = `
    <div><span>Pendientes</span><strong>${queues.pending}</strong></div>
    <div><span>Procesando</span><strong>${queues.processing}</strong></div>
    <div><span>Completados</span><strong>${queues.completed}</strong></div>
    <div><span>Fallidos 24 h</span><strong>${queues.failed}</strong></div>
    <div><span>Reintentos</span><strong>${queues.retries}</strong></div>
  `;
  $("#diagnosticsExternal").innerHTML = `
    <div><span>Ultimo backup</span><strong>${data.backups.last_success ? new Date(data.backups.last_success).toLocaleString() : "Sin backup"}</strong></div>
    <div><span>Backups disponibles</span><strong>${data.backups.available}</strong></div>
    <div><span>Storage</span><strong>${data.storage?.label || "No configurado"}</strong></div>
    <div><span>Disco libre</span><strong>${data.storage?.disk_free_percent ?? 0}%</strong></div>
    <div><span>Archivos almacenados</span><strong>${data.storage?.files || 0}</strong></div>
    <div><span>Webhook email 24 h</span><strong>${data.webhooks.items.email.total || 0}</strong></div>
    <div><span>Webhook WhatsApp 24 h</span><strong>${data.webhooks.items.whatsapp.total || 0}</strong></div>
    <div><span>Mercado Pago</span><strong>No configurado</strong></div>
  `;
  const eventHealth = data.event_health;
  $("#diagnosticsEventHealth").innerHTML = `
    <div><span>Eventos activos</span><strong>${eventHealth.active_events}</strong></div>
    <div><span>Participantes conectados</span><strong>${eventHealth.connected_participants}</strong></div>
    <div><span>Operadores conectados</span><strong>${eventHealth.active_operators}</strong></div>
    <div><span>Terminales activas</span><strong>${eventHealth.active_terminals}</strong></div>
    <div><span>Terminales inactivas</span><strong>${eventHealth.inactive_terminals}</strong></div>
  `;
  $("#diagnosticsAlerts").innerHTML = data.alerts.map((alert) => (
    `<div class="alert ${alert.severity}"><strong>${alert.severity}</strong> ${alert.message}</div>`
  )).join("") || `<div class="alert success">Sin alertas tecnicas activas.</div>`;
  renderDiagnosticsLogs();
}

async function loadSimulator() {
  if (!state.eventId || state.authUser?.role !== "Super Admin") return;
  state.simulator = await api(`/api/simulator/status?event_id=${state.eventId}`);
  const item = state.simulator;
  $("#simulatorStatus").innerHTML = `
    <div><strong>${currentProjectType() === "ticketing" ? "Ticketing" : "Conference"}</strong><span>Vertical</span></div>
    <div><strong>${item.status || "stopped"}</strong><span>Estado</span></div>
    <div><strong>${item.mode || "medium"}</strong><span>Modo</span></div>
    <div><strong>${item.participants_active || 0}</strong><span>Participantes activos</span></div>
    <div><strong>${item.accesses_per_minute || 0}</strong><span>Accesos/min</span></div>
    <div><strong>${item.rejections_per_minute || 0}</strong><span>Rechazos/min</span></div>
    <div><strong>${item.active_terminals || 0}</strong><span>Terminales</span></div>
  `;
}

async function controlSimulator(action) {
  const form = $("#simulatorForm");
  const data = formData(form);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  data.action = action;
  try {
    const result = await api("/api/simulator/control", { method: "POST", body: JSON.stringify(data) });
    $("#simulatorNotice").innerHTML = `<div class="panel success">Simulador ${result.status}.</div>`;
    await loadSimulator();
  } catch (err) {
    $("#simulatorNotice").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

const visualizationLabels = {
  accesses: "Accesos por minuto",
  registrations: "Inscripciones por hora",
  accreditations: "Acreditaciones por hora",
  communications: "Comunicaciones por hora",
  certificates: "Certificados emitidos",
};

function renderVisualizationLine(rows) {
  const target = $("#visualizationTimeSeries");
  const list = (rows || []).slice(-40);
  if (!list.length) {
    target.innerHTML = `<p class="empty">Todavia no hay datos para este periodo.</p>`;
    return;
  }
  const width = 720;
  const height = 210;
  const max = Math.max(...list.map((row) => Number(row.value || 0)), 1);
  const points = list.map((row, index) => {
    const x = list.length === 1 ? width / 2 : index * width / (list.length - 1);
    const y = height - 20 - (Number(row.value || 0) / max) * (height - 44);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const guides = [0.25, 0.5, 0.75].map((position) => {
    const y = Math.round(height * position);
    return `<line x1="0" y1="${y}" x2="${width}" y2="${y}"></line>`;
  }).join("");
  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="Serie temporal">
      <g class="viz-grid-lines">${guides}</g>
      <polyline points="${points}"></polyline>
      ${list.map((row, index) => {
        const [x, y] = points.split(" ")[index].split(",");
        return `<circle cx="${x}" cy="${y}" r="4"><title>${escapeHtml(row.label)}: ${Number(row.value || 0)}</title></circle>`;
      }).join("")}
    </svg>
    <div class="viz-axis">
      ${list.filter((_row, index) => index === 0 || index === list.length - 1 || index === Math.floor(list.length / 2))
        .map((row) => `<span>${escapeHtml(String(row.label || "").slice(5))}</span>`).join("")}
    </div>
  `;
}

function renderVisualizationHeatmap(rows) {
  const list = rows || [];
  const max = Math.max(...list.map((row) => Number(row.percentage ?? row.value ?? 0)), 1);
  $("#visualizationHeatmapGrid").innerHTML = list.slice(0, 20).map((row) => {
    const raw = Number(row.percentage ?? row.value ?? 0);
    const intensity = Math.max(0.12, raw / max);
    return `<article style="--heat:${intensity.toFixed(2)}">
      <strong>${escapeHtml(row.label || "Sin dato")}</strong>
      <span>${raw}${row.percentage !== undefined ? "%" : ""}</span>
      ${row.capacity !== undefined ? `<small>${Number(row.value || 0)} / ${Number(row.capacity || 0)}</small>` : ""}
    </article>`;
  }).join("") || `<p class="empty">Sin datos para construir el mapa.</p>`;
}

function renderVisualizationFunnel(rows) {
  const max = Math.max(...(rows || []).map((row) => Number(row.value || 0)), 1);
  $("#visualizationFunnel").innerHTML = (rows || []).map((row, index) => `
    <article style="--funnel-width:${Math.max(18, Number(row.value || 0) / max * 100)}%">
      <div>
        <span>${index + 1}</span>
        <strong>${escapeHtml(row.label)}</strong>
        <small>${Number(row.conversion || 0)}% del inicio</small>
      </div>
      <b>${Number(row.value || 0)}</b>
      <i><em></em></i>
      ${index ? `<small class="viz-loss">Perdida: ${Number(row.loss || 0)}</small>` : ""}
    </article>
  `).join("");
}

function renderVisualizationRanking(rows) {
  const list = rows || [];
  const max = Math.max(...list.map((row) => Number(row.value || 0)), 1);
  $("#visualizationRanking").innerHTML = list.slice(0, 8).map((row, index) => `
    <div class="viz-ranking-row">
      <span>${index + 1}</span>
      <div><strong>${escapeHtml(row.label)}</strong><i><b style="--w:${Number(row.value || 0) / max * 100}%"></b></i></div>
      <em>${Number(row.value || 0)}</em>
    </div>
  `).join("") || `<p class="empty">Sin actividad suficiente para el ranking.</p>`;
}

function renderVisualizationScatter(rows) {
  const list = (rows || []).slice(0, 24);
  const maxX = Math.max(...list.map((row) => Number(row.x || 0)), 1);
  const maxY = Math.max(...list.map((row) => Number(row.y || 0)), 1);
  $("#visualizationScatter").innerHTML = list.length ? `
    <div class="viz-scatter-stage">
      <span class="viz-scatter-y">Asistencia</span>
      ${list.map((row) => {
        const x = 8 + Number(row.x || 0) / maxX * 84;
        const y = 92 - Number(row.y || 0) / maxY * 82;
        return `<i style="left:${x}%;top:${y}%"><title>${escapeHtml(row.label)}: ${row.y}/${row.x}</title></i>`;
      }).join("")}
      <span class="viz-scatter-x">Inscripcion</span>
    </div>
  ` : `<p class="empty">Sin datos comparables.</p>`;
}

function renderVisualization() {
  const data = state.visualization;
  if (!data) return;
  const ticketing = data.project_type === "ticketing";
  $("#visualizationVerticalNotice")?.classList.toggle("hidden", !ticketing);
  if (ticketing) {
    $("#visualizationVerticalNotice").innerHTML = `
      <span class="eyebrow">Dashboard Ticketing</span>
      <h2>Modelo visual preparado</h2>
      <p>Ventas, sectores, ocupacion y canales se incorporaran cuando exista el modulo Ticketing. Los componentes actuales permanecen aislados.</p>
    `;
  }
  const forecast = data.forecast || {};
  $("#visualizationForecast").innerHTML = `
    <article><span>Ritmo de inscripcion</span><strong>${forecast.registration_rate_per_hour || 0}/h</strong><small>Tendencia reciente</small></article>
    <article><span>Proyeccion final</span><strong>${forecast.expected_final_registrations || 0}</strong><small>Sobre ${forecast.capacity || "sin limite"}</small></article>
    <article><span>Ritmo de acceso</span><strong>${forecast.access_rate_per_minute || 0}/min</strong><small>Ultimos minutos</small></article>
    <article><span>Ocupacion estimada</span><strong>${forecast.estimated_room_occupancy || 0}%</strong><small>Promedio de salas</small></article>
  `;
  $("#visualizationForecastDetail").innerHTML = `
    <div><span>Inscripciones actuales</span><strong>${forecast.current_registrations || 0}</strong></div>
    <div><span>Proyeccion final</span><strong>${forecast.expected_final_registrations || 0}</strong></div>
    <div><span>Tiempo a cupo</span><strong>${forecast.hours_to_capacity == null ? "Sin riesgo" : `${forecast.hours_to_capacity} h`}</strong></div>
    <div><span>Ocupacion esperada</span><strong>${forecast.estimated_room_occupancy || 0}%</strong></div>
  `;
  const seriesKey = $("#visualizationSeries")?.value || "accesses";
  const seriesRows = data.series?.[seriesKey] || [];
  $("#visualizationSeriesTitle").textContent = visualizationLabels[seriesKey] || "Serie temporal";
  $("#visualizationSeriesTotal").textContent = seriesRows.reduce((total, row) => total + Number(row.value || 0), 0);
  renderVisualizationLine(seriesRows);
  const heatKey = $("#visualizationHeatmap")?.value || "rooms";
  renderVisualizationHeatmap(data.heatmaps?.[heatKey] || []);
  renderVisualizationFunnel(data.funnel || []);
  renderVisualizationRanking(data.rankings?.activities || []);
  renderVisualizationScatter(data.scatter?.attendance_vs_registration || []);
  $("#visualizationAlerts").innerHTML = (data.predictive_alerts || []).map((alert) => `
    <article class="${escapeHtml(alert.level || "warning")}">
      <strong>${escapeHtml(alert.title)}</strong>
      <span>${escapeHtml(alert.message)}</span>
    </article>
  `).join("") || `<article class="healthy"><strong>Operacion estable</strong><span>No se detectan riesgos predictivos.</span></article>`;
  setHref("#visualizationNocLink", state.eventId ? `/noc.html?event_id=${state.eventId}&refresh=10` : "#");
}

async function loadVisualization(force = false) {
  if (!state.eventId || !["Super Admin", "Productor", "Coordinador"].includes(state.authUser?.role)) return;
  const dashboard = $("#visualizationDashboard")?.value || "operational";
  const period = $("#visualizationPeriod")?.value || "event";
  $("#visualizationNotice").innerHTML = `<div class="panel">Actualizando visualizaciones...</div>`;
  try {
    state.visualization = await api(`/api/data-visualization?event_id=${state.eventId}&dashboard=${dashboard}&period=${period}&force=${force ? 1 : 0}`);
    const layouts = await api(`/api/data-visualization/layouts?event_id=${state.eventId}`);
    state.visualizationLayouts = layouts.items || [];
    $("#visualizationNotice").innerHTML = "";
    renderVisualization();
    renderVisualizationLayouts();
  } catch (err) {
    $("#visualizationNotice").innerHTML = `<div class="panel danger">${escapeHtml(err.message)}</div>`;
  }
}

function renderVisualizationLayouts() {
  $("#visualizationLayouts").innerHTML = state.visualizationLayouts.map((layout) => `
    <button type="button" class="ghost viz-layout-button" data-layout-id="${layout.id}">
      <strong>${escapeHtml(layout.name)}</strong>
      <span>${escapeHtml(layout.dashboard)} / ${escapeHtml(layout.period)}${Number(layout.is_default) ? " / predeterminado" : ""}</span>
    </button>
  `).join("") || `<span class="empty">Todavia no guardaste layouts.</span>`;
  $$(".viz-layout-button").forEach((button) => button.addEventListener("click", () => {
    const layout = state.visualizationLayouts.find((item) => Number(item.id) === Number(button.dataset.layoutId));
    if (!layout) return;
    $("#visualizationDashboard").value = layout.dashboard;
    $("#visualizationPeriod").value = layout.period;
    $("#visualizationLayoutMode").value = layout.mode;
    loadVisualization();
  }));
}

async function saveVisualizationLayout() {
  const name = $("#visualizationLayoutName").value.trim();
  if (!name) {
    $("#visualizationNotice").innerHTML = `<div class="panel danger">Escribi un nombre para el layout.</div>`;
    return;
  }
  try {
    await api("/api/data-visualization/layouts", {
      method: "POST",
      body: JSON.stringify({
        event_id: state.eventId,
        name,
        dashboard: $("#visualizationDashboard").value,
        period: $("#visualizationPeriod").value,
        widgets: (state.visualization?.widgets || []).join(","),
        mode: $("#visualizationLayoutMode").value,
        is_default: $("#visualizationLayoutDefault").checked,
      }),
    });
    $("#visualizationLayoutName").value = "";
    $("#visualizationNotice").innerHTML = `<div class="panel success">Layout guardado.</div>`;
    const layouts = await api(`/api/data-visualization/layouts?event_id=${state.eventId}`);
    state.visualizationLayouts = layouts.items || [];
    renderVisualizationLayouts();
  } catch (err) {
    $("#visualizationNotice").innerHTML = `<div class="panel danger">${escapeHtml(err.message)}</div>`;
  }
}

function currentEvent() {
  return state.events.find((event) => Number(event.id) === Number(state.eventId));
}

function currentProjectType() {
  return String(currentEvent()?.project_type || "conference").toLowerCase();
}

function currentProjectModules() {
  if (currentProjectType() === "ticketing") {
    return {
      registration: false,
      reception: false,
      agenda: false,
      access: false,
      ticketing: true,
    };
  }
  return {
    registration: true,
    reception: true,
    agenda: true,
    access: true,
    ticketing: false,
  };
}

function eventFeature(name, fallback = true) {
  const event = currentEvent();
  if (!event || event[name] === undefined || event[name] === null) return fallback;
  return Number(event[name]) === 1;
}

function renderFeatureVisibility() {
  const modules = currentProjectModules();
  const activitiesOn = eventFeature("activities_enabled", true);
  const capacityOn = eventFeature("capacity_control_enabled", true);
  const waitlistOn = eventFeature("waitlist_enabled", false);
  document.querySelector('[data-view="register"]')?.classList.toggle("hidden", !modules.registration);
  document.querySelector('[data-view="reception"]')?.classList.toggle("hidden", !modules.reception);
  document.querySelector('[data-view="agenda"]')?.classList.toggle("hidden", !activitiesOn || !modules.agenda);
  document.querySelector('[data-view="access"]')?.classList.toggle("hidden", !modules.access);
  $("#agenda")?.classList.toggle("hidden", !activitiesOn || !modules.agenda);
  $("#displayConfigForm")?.closest(".panel")?.classList.toggle("hidden", !activitiesOn);
  $("#publicDisplayLink")?.classList.toggle("hidden", !activitiesOn);
  $$(".capacity-feature").forEach((node) => node.classList.toggle("hidden", !capacityOn));
  $$(".waitlist-feature").forEach((node) => node.classList.toggle("hidden", !waitlistOn));
  $("#ticketingModeNotice")?.classList.toggle("hidden", !modules.ticketing);
  $("#dashboard .layout")?.classList.toggle("ticketing-layout", modules.ticketing);
  const activeView = $(".view.active")?.id;
  if (
    (activeView === "register" && !modules.registration)
    || (activeView === "reception" && !modules.reception)
    || (activeView === "agenda" && !modules.agenda)
    || (activeView === "access" && !modules.access)
  ) {
    setView("dashboard");
  }
}

function updateControlRoomLink() {
  const blocks = $$(".visual-block-picker input:checked").map((input) => input.value).join(",");
  const refresh = $("#controlRoomRefresh")?.value || "10";
  const theme = $("#controlRoomDark")?.checked ? "dark" : "light";
  const compact = $("#controlRoomCompact")?.checked ? "1" : "0";
  const rotate = $("#controlRoomRotate")?.value || "0";
  const maxRooms = $("#controlRoomMaxRooms")?.value || "6";
  const maxAlerts = $("#controlRoomMaxAlerts")?.value || "4";
  if ($("#controlRoomLink")) {
    $("#controlRoomLink").href = state.eventId ? `/reports-display?event_id=${state.eventId}&refresh=${refresh}&theme=${theme}&compact=${compact}&rotate=${rotate}&max_rooms=${maxRooms}&max_alerts=${maxAlerts}&blocks=${encodeURIComponent(blocks)}` : "#";
  }
  setHref("#nocLink", state.eventId ? `/noc.html?event_id=${state.eventId}&refresh=${refresh}` : "#");
}

function updateMetrics() {
  const event = currentEvent();
  const total = Number(event?.accreditation_count || 0);
  const checked = Number(event?.checked_in_count || 0);
  $("#mTotal").textContent = total;
  $("#mIn").textContent = checked;
  $("#mPending").textContent = Math.max(total - checked, 0);
  setHref("#exportLink", state.eventId ? `/api/export.csv?event_id=${state.eventId}` : "#");
  setHref("#exportJsonLink", state.eventId ? `/api/export.json?event_id=${state.eventId}` : "#");
  setHref("#exportReservationsLink", state.eventId ? `/api/reservations.csv?event_id=${state.eventId}` : "#");
  setHref("#exportAttendancesLink", state.eventId ? `/api/attendances.csv?event_id=${state.eventId}` : "#");
  setHref("#exportCertificatesLink", state.eventId ? `/api/certificate-eligibility.csv?event_id=${state.eventId}&status=eligible` : "#");
  setHref("#exportCaptationLink", state.eventId ? `/api/captation.csv?event_id=${state.eventId}` : "#");
  setHref("#reportsExportCaptationLink", state.eventId ? `/api/captation.csv?event_id=${state.eventId}` : "#");
  setHref("#reportsExportJsonLink", state.eventId ? `/api/export.json?event_id=${state.eventId}` : "#");
  setHref("#reportsExecutivePdfLink", state.eventId ? `/api/reports/executive.pdf?event_id=${state.eventId}` : "#");
  setHref("#reportsAccreditationsLink", state.eventId ? `/api/export.csv?event_id=${state.eventId}` : "#");
  setHref("#reportsReservationsLink", state.eventId ? `/api/reservations.csv?event_id=${state.eventId}` : "#");
  setHref("#reportsAttendancesLink", state.eventId ? `/api/attendances.csv?event_id=${state.eventId}` : "#");
  setHref("#reportsEligibilityLink", state.eventId ? `/api/certificate-eligibility.csv?event_id=${state.eventId}&status=eligible` : "#");
  setHref("#exportStructureLink", state.eventId ? `/api/event-structure.json?event_id=${state.eventId}` : "#");
  setHref("#exportAgendaLink", state.eventId ? `/api/agenda.csv?event_id=${state.eventId}` : "#");
  setHref("#exportAgendaIcsLink", state.eventId ? `/api/agenda.ics?event_id=${state.eventId}` : "#");
  setHref("#publicEventLink", state.eventId ? `/e.html?event_id=${state.eventId}` : "#");
  setHref("#publicDisplayLink", state.eventId ? `/display.html?event_id=${state.eventId}` : "#");
  setHref("#backupLink", state.eventId ? `/api/backup?event_id=${state.eventId}` : "/api/backup");
  setHref("#reportsBackupLink", state.eventId ? `/api/backup?event_id=${state.eventId}` : "/api/backup");
  updateControlRoomLink();
  renderFeatureVisibility();
  renderLandingConfig();
  renderWaitingRoomConfig();
}

function renderLandingConfig() {
  const preview = $("#landingPreview");
  if (!preview) return;
  const event = currentEvent();
  const meta = $("#landingImageMeta");
  if (event?.landing_image_data) {
    preview.classList.add("has-image");
    preview.style.backgroundImage = `linear-gradient(90deg, rgba(23, 33, 43, 0.56), rgba(23, 33, 43, 0.12)), url("${event.landing_image_data}")`;
    preview.innerHTML = `<strong>Imagen personalizada cargada</strong><span>${event.landing_image_name || "landing"} · ${event.landing_image_type || "imagen"}</span>`;
    meta.textContent = `Actualizada: ${event.landing_image_updated_at || "-"}`;
  } else {
    preview.classList.remove("has-image");
    preview.style.backgroundImage = "";
    preview.innerHTML = `<strong>Fondo BITORA por defecto</strong><span>Arena #D2B89A · 16:9 · zona segura central</span>`;
    meta.textContent = "Sin imagen personalizada";
  }
}

function renderWaitingRoomConfig() {
  const form = $("#waitingRoomConfigForm");
  const event = currentEvent();
  if (!form || !event) return;
  form.waiting_room_enabled.checked = Number(event.waiting_room_enabled || 0) === 1;
  form.waiting_room_open_at.value = String(event.waiting_room_open_at || "").slice(0, 16);
  form.users_allowed_per_minute.value = event.users_allowed_per_minute || 60;
  form.turn_duration_minutes.value = event.turn_duration_minutes || 10;
  form.show_position.checked = Number(event.show_waiting_position ?? 1) === 1;
  form.show_estimated_time.checked = Number(event.show_estimated_time ?? 1) === 1;
  form.waiting_message.value = event.waiting_message || "";
}

async function saveWaitingRoomConfig(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  data.waiting_room_enabled = form.waiting_room_enabled.checked;
  data.show_position = form.show_position.checked;
  data.show_estimated_time = form.show_estimated_time.checked;
  try {
    await api("/api/waiting-room/config", { method: "POST", body: JSON.stringify(data) });
    $("#waitingRoomConfigNotice").innerHTML = `<div class="panel success">Sala de espera actualizada.</div>`;
    await loadEvents();
  } catch (err) {
    $("#waitingRoomConfigNotice").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

function readLandingImageFile(file) {
  return new Promise((resolve, reject) => {
    if (!file) return reject(new Error("Selecciona una imagen"));
    const validTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!validTypes.includes(file.type)) return reject(new Error("Formato no permitido. Usa JPG, JPEG, PNG o WEBP"));
    if (file.size > 3 * 1024 * 1024) return reject(new Error("Imagen demasiado pesada. Maximo 3 MB"));
    const reader = new FileReader();
    reader.onload = () => {
      const image = new Image();
      image.onload = () => {
        if (image.naturalWidth < 800 || image.naturalHeight < 450) {
          reject(new Error("Resolucion minima 800 x 450. Recomendado 1920 x 1080"));
          return;
        }
        resolve({ dataUrl: reader.result, width: image.naturalWidth, height: image.naturalHeight });
      };
      image.onerror = () => reject(new Error("No se pudo leer la imagen"));
      image.src = reader.result;
    };
    reader.onerror = () => reject(new Error("No se pudo leer el archivo"));
    reader.readAsDataURL(file);
  });
}

async function saveLandingImage(event) {
  event.preventDefault();
  const notice = $("#landingConfigNotice");
  const file = $("#landingImageFile")?.files?.[0];
  try {
    const image = await readLandingImageFile(file);
    await api("/api/event-landing", {
      method: "POST",
      body: JSON.stringify({
        event_id: state.eventId,
        actor: state.currentUser,
        action: "upload",
        filename: file.name,
        image_data: image.dataUrl,
      }),
    });
    notice.innerHTML = `<div class="panel success">Imagen de landing guardada (${image.width} x ${image.height}).</div>`;
    $("#landingImageFile").value = "";
    await loadEvents();
  } catch (err) {
    notice.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function deleteLandingImage() {
  const notice = $("#landingConfigNotice");
  if (!state.eventId) return;
  if (!confirm("Eliminar imagen personalizada de la landing? Se usara el fondo BITORA por defecto.")) return;
  try {
    await api("/api/event-landing", {
      method: "POST",
      body: JSON.stringify({ event_id: state.eventId, actor: state.currentUser, action: "delete" }),
    });
    notice.innerHTML = `<div class="panel success">Imagen eliminada. La landing usara el fondo BITORA por defecto.</div>`;
    await loadEvents();
  } catch (err) {
    notice.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function loadAccreditations() {
  if (!state.eventId) return;
  const q = encodeURIComponent($("#searchInput")?.value || "");
  const rows = filterAccreditations(await api(`/api/accreditations?event_id=${state.eventId}&q=${q}`));
  state.accreditations = await api(`/api/accreditations?event_id=${state.eventId}`);
  $("#accreditations").innerHTML = rows.map((row) => renderAccreditationCard(row)).join("") || `<p class="empty">No hay acreditados para mostrar.</p>`;
  bindAccreditationActions($("#accreditations"));
  renderReservationSelectors();
}

function renderAccreditationCard(row, compact = false) {
  const certificateLabel = Number(row.elegible_certificado || 0) ? "Certificado: elegible" : "Certificado: pendiente";
  const attendanceLabel = Number(row.requiere_asistencia || 0) ? "Asistencia requerida" : "Asistencia no requerida";
  const detailLine = [
    row.dni ? `DNI ${row.dni}` : "",
    row.phone ? `Tel. ${row.phone}` : "",
    row.company || "",
  ].filter(Boolean).join(" - ");
  const quickActions = `
    <a class="button ghost" href="/p.html?token=${row.token}" target="_blank">Ver QR</a>
    <button type="button" class="print-one" data-token="${row.token}">Imprimir</button>
    <button type="button" class="manual-checkin" data-token="${row.token}">Acreditar</button>
    <button type="button" class="edit-accreditation" data-id="${row.id}">Editar</button>
    ${row.phone ? `<a class="button ghost" href="${whatsappLink(row)}" target="_blank">WhatsApp</a>` : ""}
  `;
  const fullActions = `
    <a class="button ghost" href="/p.html?token=${row.token}" target="_blank">Credencial</a>
    <a class="button ghost" href="/api/qr.svg?token=${row.token}" target="_blank">Ver QR</a>
    <a class="button ghost" href="/api/qr.svg?token=${row.token}" download="${row.token}.svg">Descargar QR</a>
    <button type="button" class="print-one" data-token="${row.token}">Imprimir</button>
    <button type="button" class="wristband-one" data-token="${row.token}">Pulsera</button>
    <button type="button" class="certificate-one" data-token="${row.token}">Certificado</button>
    <button type="button" class="edit-accreditation" data-id="${row.id}">Editar</button>
    <button type="button" class="manual-checkin" data-token="${row.token}">Acreditar</button>
    ${row.status === "cancelled"
      ? `<button type="button" class="status-accreditation" data-id="${row.id}" data-status="active">Reactivar</button>`
      : `<button type="button" class="status-accreditation danger-button" data-id="${row.id}" data-status="cancelled">Cancelar</button>`}
    ${row.phone ? `<a class="button ghost" href="${whatsappLink(row)}" target="_blank">WhatsApp</a>` : ""}
    ${row.email ? `<a class="button ghost" href="mailto:${row.email}?subject=Credencial%20${encodeURIComponent(row.event_name || "BITORA")}&body=${encodeURIComponent(`Hola ${row.first_name || ""}, tu portal es ${location.origin}/p.html?token=${row.token}`)}">Email</a>` : ""}
    <a class="button ghost" href="/p.html?token=${row.token}" target="_blank">Reenviar portal</a>
    <button type="button" class="audit-focus" data-token="${row.token}">Historial</button>
  `;
  return `
    <article class="row ${compact ? "compact-row" : ""}">
      <div>
        <strong>${row.first_name} ${row.last_name}</strong>
        <span>${row.email}</span>
        <span>${detailLine || "Sin datos complementarios"}</span>
      </div>
      <code>${row.token}</code>
      <span class="pill">${row.type}</span>
      <div class="status-stack">
        <span class="status ${row.checked_in_at ? "ok" : ""}">${accreditationStatusLabel(row)}</span>
        <span class="status">${certificateLabel}</span>
        <span class="status">${attendanceLabel}</span>
      </div>
      <div class="row-actions">
        ${compact ? quickActions : fullActions}
      </div>
    </article>
  `;
}

function bindAccreditationActions(scope = document) {
  scope.querySelectorAll(".manual-checkin").forEach((button) => button.addEventListener("click", () => manualCheckIn(button.dataset.token)));
  scope.querySelectorAll(".print-one").forEach((button) => button.addEventListener("click", () => printOneCredential(button.dataset.token)));
  scope.querySelectorAll(".wristband-one").forEach((button) => button.addEventListener("click", () => printOneWristband(button.dataset.token)));
  scope.querySelectorAll(".certificate-one").forEach((button) => button.addEventListener("click", () => printManualCertificate(button.dataset.token)));
  scope.querySelectorAll(".edit-accreditation").forEach((button) => button.addEventListener("click", () => openAccreditationEditor(button.dataset.id)));
  scope.querySelectorAll(".status-accreditation").forEach((button) => button.addEventListener("click", () => changeAccreditationStatus(button.dataset.id, button.dataset.status)));
  scope.querySelectorAll(".audit-focus").forEach((button) => button.addEventListener("click", () => {
    setView("audit");
    loadAudit();
  }));
}

async function loadQuickReception() {
  if (!state.eventId) return;
  const box = $("#quickReceptionResult");
  const term = ($("#quickReceptionSearch")?.value || "").trim();
  if (!term) {
    box.innerHTML = `<p class="empty">Busca un participante para ver acciones rapidas.</p>`;
    return;
  }
  const rows = await api(`/api/accreditations?event_id=${state.eventId}&q=${encodeURIComponent(term)}`);
  box.innerHTML = rows.slice(0, 5).map((row) => renderAccreditationCard(row, true)).join("") || `<p class="empty">Sin resultados para esa busqueda.</p>`;
  bindAccreditationActions(box);
}

async function quickValidateReceptionToken() {
  const token = ($("#quickReceptionToken")?.value || "").trim();
  const box = $("#quickReceptionResult");
  if (!token) {
    box.innerHTML = `<div class="panel danger">Pegá un token o QR para acreditar.</div>`;
    return;
  }
  await manualCheckIn(token);
  $("#quickReceptionToken").value = "";
  await loadQuickReception();
}

function printUrl(extra = {}) {
  const params = new URLSearchParams({
    event_id: state.eventId,
    q: $("#searchInput")?.value || "",
    status: $("#statusFilter")?.value || "",
    type: $("#typeFilter")?.value || "",
    ...extra,
  });
  return `/print.html?${params.toString()}`;
}

function printFilteredCredentials() {
  window.open(printUrl(), "_blank");
}

function printOneCredential(token) {
  window.open(printUrl({ q: token, status: "", type: "" }), "_blank");
}

function printOneWristband(token) {
  window.open(printUrl({ q: token, status: "", type: "", mode: "wristband" }), "_blank");
}

async function printManualCertificate(token) {
  const notice = $("#receptionNotice");
  const url = `/api/certificate.pdf?token=${encodeURIComponent(token)}&manual=1`;
  try {
    const response = await fetch(url);
    if (!response.ok) {
      let message = "Certificado no disponible para este acreditado.";
      try {
        const data = await response.json();
        message = data.error || message;
      } catch (err) {
        // Algunos errores del servidor llegan como HTML; mostramos mensaje operativo.
      }
      notice.innerHTML = `<div class="panel danger">${message}</div>`;
      return;
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    window.open(objectUrl, "_blank");
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    notice.innerHTML = `<div class="panel success">Certificado preparado para imprimir.</div>`;
  } catch (err) {
    notice.innerHTML = `<div class="panel danger">No se pudo preparar el certificado.</div>`;
  }
}

function accreditationStatusLabel(row) {
  if (row.status === "cancelled") return "Cancelado";
  return row.checked_in_at ? "Acreditado" : "Pendiente";
}

function filterAccreditations(rows) {
  const status = $("#statusFilter")?.value || "";
  const type = $("#typeFilter")?.value || "";
  return rows.filter((row) => {
    const statusOk = !status
      || (status === "cancelled" && row.status === "cancelled")
      || (status === "checked" && Boolean(row.checked_in_at) && row.status !== "cancelled")
      || (status === "pending" && !row.checked_in_at && row.status !== "cancelled");
    const typeOk = !type || row.type === type;
    return statusOk && typeOk;
  });
}

function whatsappLink(row) {
  const phone = String(row.phone || "").replace(/\D/g, "");
  const url = `${location.origin}/p.html?token=${row.token}`;
  const text = `Hola ${row.first_name}, tu credencial para ${row.event_name}: ${url}`;
  return `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
}

async function loadTypes() {
  if (!state.eventId) return;
  state.types = await api(`/api/types?event_id=${state.eventId}`);
  $("#typeSelect").innerHTML = state.types
    .filter((row) => Number(row.access_enabled) === 1)
    .map((row) => `<option>${row.name}</option>`)
    .join("");
  $("#editTypeSelect").innerHTML = state.types
    .map((row) => `<option>${row.name}</option>`)
    .join("");
  const typeFilter = $("#typeFilter");
  if (typeFilter) {
    const selected = typeFilter.value;
    typeFilter.innerHTML = `<option value="">Todos los tipos</option>` + state.types
      .map((row) => `<option value="${row.name}">${row.name}</option>`)
      .join("");
    typeFilter.value = state.types.some((row) => row.name === selected) ? selected : "";
  }
  $("#typesList").innerHTML = state.types.map((row) => {
    const capacity = Number(row.capacity || 0);
    const used = Number(row.used || 0);
    const label = capacity ? `${used}/${capacity}` : `${used}/sin limite`;
    const isFull = capacity && used >= capacity;
    return `
      <form class="type-row ${isFull ? "full" : ""}" data-name="${row.name}">
        <strong>${row.name}</strong>
        <span>${label}</span>
        <input name="capacity" type="number" min="0" value="${capacity}" aria-label="Cupo ${row.name}">
        <label class="toggle">
          <input name="access_enabled" type="checkbox" ${Number(row.access_enabled) ? "checked" : ""}>
          Acceso
        </label>
        <button>Guardar</button>
      </form>
    `;
  }).join("");
  $$(".type-row").forEach((form) => form.addEventListener("submit", saveType));
}

async function loadUsers() {
  state.users = await api("/api/users");
  const select = $("#currentUserSelect");
  select.innerHTML = state.users.map((row) => `<option value="${row.name}">${row.name} - ${row.role}</option>`).join("");
  if (state.authUser) {
    state.currentUser = state.authUser.name;
    select.disabled = true;
  } else if (!state.users.some((row) => row.name === state.currentUser)) {
    state.currentUser = state.users[0]?.name || "Admin";
  }
  select.value = state.currentUser;
  $("#operator").value = state.currentUser;
  $("#usersList").innerHTML = state.users.map((row) => `
    <div class="mini-row">
      <strong>${row.name}</strong>
      <span>${row.role}</span>
    </div>
  `).join("");
}

async function loadNetworkInfo() {
  state.networkInfo = await api("/api/network-info");
  const info = state.networkInfo;
  $("#networkStatus").innerHTML = `
    <div class="network-grid">
      <div><strong>${info.local_url}</strong><span>Esta PC</span></div>
      <div><strong>${info.network_url}</strong><span>Otra PC misma red</span></div>
      <div><strong>${info.require_login ? "Protegido" : "Local"}</strong><span>Consola</span></div>
    </div>
    <div class="network-actions">
      <a class="button" href="${info.local_url}/scan.html?event_id=${state.eventId || ""}" target="_blank">Escaner movil en esta PC</a>
      <a class="button ghost" href="${info.network_url}/scan.html?event_id=${state.eventId || ""}" target="_blank">Escaner movil en red</a>
    </div>
  `;
}

async function loadAudit() {
  if (!state.eventId) return;
  state.audit = await api(`/api/audit?event_id=${state.eventId}`);
  $("#auditList").innerHTML = state.audit.map((row) => `
    <article class="audit-row">
      <div>
        <strong>${row.action}</strong>
        <span>${row.actor || "sistema"} - ${new Date(row.created_at).toLocaleString()}</span>
      </div>
      <code>${row.entity_type}${row.entity_id ? ` #${row.entity_id}` : ""}</code>
    </article>
  `).join("") || `<p class="empty">Todavia no hay auditoria para este evento.</p>`;
}

async function loadCommunications() {
  if (!state.eventId) return;
  state.communications = await api(`/api/communications?event_id=${state.eventId}`);
  const stats = state.communications.stats || {};
  const providers = state.communications.providers || {};
  const queueMetrics = state.communications.queue_metrics || {};
  const assistantMetrics = state.communications.assistant_metrics || {};
  $("#communicationProviders").innerHTML = `
    <div><strong>${state.communications.mode === "demo" ? "DEMO" : "REAL"}</strong><span>Modo</span></div>
    <div><strong>${providers.email?.provider || "demo"}</strong><span>Email ${providers.email?.ready ? "listo" : "demo"}</span></div>
    <div><strong>${providers.whatsapp?.provider || "demo"}</strong><span>WhatsApp ${providers.whatsapp?.ready ? "listo" : "demo"}</span></div>
  `;
  $("#communicationStats").innerHTML = `
    <div><strong>${Number(stats.participants || 0)}</strong><span>Participantes</span></div>
    <div><strong>${Number(stats.with_email || 0)}</strong><span>Con email</span></div>
    <div><strong>${Number(stats.with_whatsapp || 0)}</strong><span>Con WhatsApp</span></div>
    <div><strong>${Number(stats.with_both || 0)}</strong><span>Con ambos</span></div>
    <div><strong>${Number(stats.with_consent || 0)}</strong><span>Con consentimiento</span></div>
  `;
  $("#communicationV5Metrics").innerHTML = `
    <div><strong>${Number(queueMetrics.emails_sent || 0)}</strong><span>Emails enviados</span></div>
    <div><strong>${Number(queueMetrics.emails_delivered || 0)}</strong><span>Emails entregados</span></div>
    <div><strong>${Number(queueMetrics.emails_bounced || 0)}</strong><span>Rebotes</span></div>
    <div><strong>${Number(queueMetrics.emails_failed || 0)}</strong><span>Email fallidos</span></div>
    <div><strong>${Number(queueMetrics.whatsapp_sent || 0)}</strong><span>WhatsApp enviados</span></div>
    <div><strong>${Number(queueMetrics.whatsapp_delivered || 0)}</strong><span>WhatsApp entregados</span></div>
    <div><strong>${Number(queueMetrics.whatsapp_read || 0)}</strong><span>WhatsApp leidos</span></div>
    <div><strong>${Number(queueMetrics.pending || 0)}</strong><span>Pendientes</span></div>
    <div><strong>${Number(queueMetrics.errors || 0)}</strong><span>Errores</span></div>
  `;
  const emailProvider = providers.email || {};
  const emailSummary = $("#emailConfigSummary");
  if (emailSummary) {
    emailSummary.innerHTML = `
      <div><strong>${emailProvider.provider || "demo"}</strong><span>Proveedor activo</span></div>
      <div><strong>${emailProvider.ready ? "Conectado" : "No configurado"}</strong><span>Estado</span></div>
      <div><strong>${emailProvider.from || "Sin remitente"}</strong><span>Remitente</span></div>
      <div><strong>${emailProvider.reply_to || "No definido"}</strong><span>Responder a</span></div>
      <div><strong>${emailProvider.last_success ? new Date(emailProvider.last_success).toLocaleString() : "Sin envios"}</strong><span>Ultimo exitoso</span></div>
      <div><strong>${emailProvider.last_error || "Sin errores"}</strong><span>Ultimo error</span></div>
    `;
  }
  const emailTestForm = $("#emailTestForm");
  if (emailTestForm) {
    emailTestForm.classList.toggle("hidden", state.authUser?.role !== "Super Admin");
  }
  $("#assistantMetrics").innerHTML = `
    <div><strong>${Number(assistantMetrics.received || 0)}</strong><span>Consultas</span></div>
    <div><strong>${Number(assistantMetrics.resolved || 0)}</strong><span>Resueltas</span></div>
    <div><strong>${Number(assistantMetrics.handoffs || 0)}</strong><span>Derivaciones</span></div>
    <div><strong>${Number(assistantMetrics.errors || 0)}</strong><span>Errores</span></div>
  `;
  $("#assistantTickets").innerHTML = (state.communications.tickets || []).map((row) => `
    <div class="mini-row">
      <strong>${row.reason || "Derivacion humana"}</strong>
      <span>${row.status} - ${new Date(row.created_at).toLocaleString()}</span>
    </div>
  `).join("") || `<p class="empty">Sin derivaciones humanas.</p>`;
  $("#communicationTemplates").innerHTML = state.communications.templates.map((row) => `
    <button type="button" class="mini-row template-pick" data-code="${row.code}" data-type="${row.tipo}" data-subject="${row.asunto}" data-content="${row.contenido}">
      <strong>${row.name}</strong>
      <span>${row.tipo}</span>
    </button>
  `).join("") || `<p class="empty">Sin plantillas.</p>`;
  $("#communicationTypeSelect").innerHTML = state.communications.templates.map((row) => (
    `<option value="${row.code}">${row.name}</option>`
  )).join("") || `<option value="aviso operativo">Aviso operativo</option>`;
  $("#communicationQueue").innerHTML = (state.communications.queue || []).map((row) => `
    <article class="audit-row">
      <div>
        <strong>${row.subject || row.template_code}</strong>
        <span>${row.first_name} ${row.last_name} - ${row.channel} - ${row.status} - ${row.provider}</span>
      </div>
      <code>${row.audience}</code>
    </article>
  `).join("") || `<p class="empty">Cola vacia.</p>`;
  $("#communicationLogs").innerHTML = state.communications.logs.map((row) => `
    <article class="audit-row">
      <div>
        <strong>${row.asunto || row.tipo}</strong>
        <span>${row.first_name} ${row.last_name} - ${row.canal} - ${row.estado} - ${new Date(row.fecha).toLocaleString()}</span>
      </div>
      <code>${row.tipo}</code>
    </article>
  `).join("") || `<p class="empty">Todavia no hay comunicaciones registradas.</p>`;
  $$(".template-pick").forEach((button) => button.addEventListener("click", () => {
    const form = $("#communicationForm");
    form.elements.type.value = button.dataset.type;
    form.elements.subject.value = button.dataset.subject;
    form.elements.content.value = button.dataset.content;
    form.dataset.templateCode = button.dataset.code;
  }));
}

async function loadDemoReal() {
  if (!state.eventId) return;
  state.demoReal = await api(`/api/demo-real?event_id=${state.eventId}`);
  const panel = $("#demoRealPanel");
  if (!panel) return;
  if (!state.demoReal.active) {
    panel.classList.add("hidden");
    return;
  }
  panel.classList.remove("hidden");
  $("#demoParticipants").innerHTML = state.demoReal.examples.map((row) => `
    <article class="mini-row demo-person">
      <div>
        <strong>${row.name}</strong>
        <span>${row.type} - ${row.company}</span>
        <code>${row.token}</code>
      </div>
      <div class="row-actions">
        <a class="button" href="${row.portal_url}" target="_blank">Abrir portal</a>
        <a class="button ghost" href="${row.qr_url}" target="_blank">Ver QR</a>
        <a class="button ghost" href="${row.portal_url}#agenda" target="_blank">Agenda</a>
        <a class="button ghost" href="${row.portal_url}#actividades" target="_blank">Inscripciones</a>
      </div>
    </article>
  `).join("");
  $("#demoGuide").innerHTML = state.demoReal.guide.map((step) => `<li>${step}</li>`).join("");
}

async function loadAgenda() {
  if (!state.eventId) return;
  const [spaces, activities, reservations, bags, display, attendanceDashboard] = await Promise.all([
    api(`/api/spaces?event_id=${state.eventId}`),
    api(`/api/activities?event_id=${state.eventId}`),
    api(`/api/reservations?event_id=${state.eventId}`),
    api(`/api/capacity-bags?event_id=${state.eventId}`),
    api(`/api/public-display?event_id=${state.eventId}`),
    api(`/api/attendance-dashboard?event_id=${state.eventId}`),
  ]);
  state.spaces = spaces;
  state.activities = activities;
  state.reservations = reservations;
  state.bags = bags;
  state.displayConfig = {
    ...(display.config || {}),
    selected_activity_ids: display.selected_activity_ids || [],
    has_selection: Boolean(display.has_selection),
  };
  state.attendanceDashboard = attendanceDashboard;
  renderDisplayConfig();
  $("#spaceSelect").innerHTML = spaces.map((row) => `<option value="${row.id}">${row.name}</option>`).join("");
  $("#spacesList").innerHTML = spaces.map((row) => `
    <div class="mini-row">
      <strong>${row.name}</strong>
      <span>${row.capacity || "sin limite"} lugares - ${row.transition_minutes} min transicion</span>
    </div>
  `).join("");
  const attendanceByActivity = Object.fromEntries((attendanceDashboard.activities || []).map((row) => [Number(row.id), row]));
  $("#activitiesList").innerHTML = activities.map((row) => {
    const attendance = attendanceByActivity[Number(row.id)] || {};
    return `
    <article class="activity-row" data-id="${row.id}">
      <time>${new Date(row.starts_at).toLocaleString()} - ${new Date(row.ends_at).toLocaleTimeString()}</time>
      <div>
        <strong>${row.title}</strong>
        <span>${row.space_name} - ${row.activity_type} - ${row.speaker || "sin disertante"}</span>
        <small>${Number(attendance.present || 0)} presentes - ${Number(attendance.absent || 0)} ausentes - ${Number(attendance.eligible || 0)} elegibles</small>
      </div>
      <span class="pill">${activityCapacityLabel(row)}</span>
      <button type="button" class="display-toggle" data-id="${row.id}">Pantalla</button>
    </article>
  `}).join("") || `<p class="empty">Todavia no hay actividades cargadas.</p>`;
  renderReservationSelectors();
  renderAccessActivitySelector();
  renderReservations();
  renderCapacityBags();
  $$(".activity-row").forEach((row) => row.addEventListener("click", (event) => {
    if (event.target.closest("a,button")) return;
    openActivityDetail(row.dataset.id);
  }));
}

function activityCapacityLabel(row) {
  if (!eventFeature("capacity_control_enabled", true)) return "Sin control de cupos";
  const confirmed = Number(row.confirmed_count || 0);
  const waitlist = Number(row.waitlist_count || 0);
  const capacity = Number(row.capacity || 0);
  const base = capacity ? `${confirmed}/${capacity}` : `${confirmed}/sin limite`;
  return waitlist && eventFeature("waitlist_enabled", false) ? `${base} + ${waitlist} espera` : base;
}

function renderDisplayConfig() {
  if (!state.displayConfig) return;
  $("#displayMode").value = state.displayConfig.mode || "airport";
  $("#displayRefresh").value = state.displayConfig.refresh_seconds || 10;
  $("#displayPaused").checked = Number(state.displayConfig.paused || 0) === 1;
  $("#displayMessageInput").value = state.displayConfig.message || "";
  const selected = new Set((state.displayConfig.selected_activity_ids || []).map(Number));
  const picker = $("#displayActivityPicker");
  if (!picker) return;
  picker.innerHTML = state.activities.map((row) => {
    const checked = selected.has(Number(row.id)) ? "checked" : "";
    return `
      <label class="display-activity-option">
        <input type="checkbox" value="${row.id}" ${checked}>
        <span>
          <strong>${row.title}</strong>
          <small>${new Date(row.starts_at).toLocaleString()} - ${row.space_name}</small>
        </span>
      </label>
    `;
  }).join("") || `<p class="empty">Todavia no hay charlas cargadas.</p>`;
}

function renderCapacityBags() {
  const byActivity = {};
  state.bags.forEach((bag) => {
    byActivity[bag.activity_title] ||= [];
    byActivity[bag.activity_title].push(bag);
  });
  $("#capacityBagsList").innerHTML = Object.entries(byActivity).map(([title, bags]) => `
    <section class="bag-group">
      <h3>${title}</h3>
      ${bags.map((bag) => `
        <form class="bag-row" data-id="${bag.id}">
          <strong>${bag.name}</strong>
          <span>${Number(bag.used || 0)}/${Number(bag.assigned_capacity || 0) || "sin limite"}</span>
          <input name="assigned_capacity" type="number" min="${Number(bag.used || 0)}" value="${Number(bag.assigned_capacity || 0)}">
          <label><input name="public_visible" type="checkbox" ${Number(bag.public_visible) ? "checked" : ""}> Publica</label>
          <label><input name="public_registration" type="checkbox" ${Number(bag.public_registration) ? "checked" : ""}> Online</label>
          <label><input name="reception_enabled" type="checkbox" ${Number(bag.reception_enabled) ? "checked" : ""}> Recepcion</label>
          <select name="status">
            <option value="active" ${bag.status === "active" ? "selected" : ""}>Activa</option>
            <option value="agotada" ${bag.status === "agotada" ? "selected" : ""}>Agotada</option>
            <option value="cerrada" ${bag.status === "cerrada" ? "selected" : ""}>Cerrada</option>
          </select>
          <button>Guardar</button>
        </form>
      `).join("")}
    </section>
  `).join("") || `<p class="empty">Sin bolsas.</p>`;
  $$(".bag-row").forEach((form) => form.addEventListener("submit", saveCapacityBag));
  $$(".display-toggle").forEach((button) => button.addEventListener("click", () => toggleDisplayItem(button.dataset.id)));
}

function renderReservationSelectors() {
  const accSelect = $("#reservationAccreditationSelect");
  const activitySelect = $("#reservationActivitySelect");
  if (!accSelect || !activitySelect) return;
  accSelect.innerHTML = state.accreditations.map((row) => (
    `<option value="${row.id}">${row.first_name} ${row.last_name} - ${row.type}</option>`
  )).join("");
  activitySelect.innerHTML = state.activities.map((row) => (
    `<option value="${row.id}">${row.title} - ${row.space_name}</option>`
  )).join("");
}

function renderAccessActivitySelector() {
  const select = $("#accessActivitySelect");
  if (!select) return;
  select.innerHTML = `<option value="">Evento general</option>` + state.activities.map((row) => (
    `<option value="${row.id}">${row.title} - ${row.space_name}</option>`
  )).join("");
}

function renderReservations() {
  const list = $("#reservationsList");
  if (!list) return;
  list.innerHTML = state.reservations.map((row) => `
    <article class="reservation-row ${row.status}">
      <strong>${row.first_name} ${row.last_name}</strong>
      <span>${row.activity_title} - ${row.space_name}</span>
      <span class="pill">${reservationStatusLabel(row.status)}</span>
      <div class="reservation-actions">
        ${row.status === "waitlisted" ? `<button type="button" class="reservation-status" data-id="${row.id}" data-status="confirmed">Promover</button>` : ""}
        ${row.status !== "cancelled" ? `<button type="button" class="reservation-status danger-button" data-id="${row.id}" data-status="cancelled">Cancelar</button>` : ""}
      </div>
    </article>
  `).join("") || `<p class="empty">Todavia no hay inscripciones.</p>`;
  list.querySelectorAll(".reservation-status").forEach((button) => (
    button.addEventListener("click", () => changeReservationStatus(button.dataset.id, button.dataset.status))
  ));
}

function reservationStatusLabel(status) {
  if (status === "confirmed") return "Confirmada";
  if (status === "cancelled") return "Cancelada";
  return "Espera";
}

async function loadAlerts() {
  if (!state.eventId) return;
  state.alerts = await api(`/api/alerts?event_id=${state.eventId}`);
  $("#alertsList").innerHTML = state.alerts.map((alert) => (
    `<div class="alert ${alert.level}">${alert.message}</div>`
  )).join("") || `<p class="empty">Sin alertas operativas.</p>`;
}

async function loadSystemStatus() {
  if (!state.eventId) return;
  state.systemStatus = await api(`/api/system-status?event_id=${state.eventId}`);
  const status = state.systemStatus;
  const backup = status.latest_backup ? status.latest_backup.name : "sin backup";
  $("#systemStatus").innerHTML = `
    <div class="system-grid">
      <div><strong>Online</strong><span>${new Date(status.server_time).toLocaleTimeString()}</span></div>
      <div><strong>${status.recent_access.total}</strong><span>Escaneos 15 min</span></div>
      <div><strong>${status.recent_access.rejected}</strong><span>Rechazos 15 min</span></div>
      <div><strong>${status.active_operators.length}</strong><span>Operadores activos</span></div>
      <div><strong>${formatBytes(status.database_size)}</strong><span>Base local</span></div>
      <div><strong>${backup}</strong><span>Ultimo backup</span></div>
      <div><strong>${status.env || "-"}</strong><span>Entorno</span></div>
      <div><strong>${status.version || "-"}</strong><span>Version</span></div>
      <div><strong>${status.database?.engine || "-"}</strong><span>Base de datos</span></div>
    </div>
    <div class="operator-list">
      ${status.active_operators.map((row) => `
        <div class="mini-row">
          <strong>${row.operator || "sin operador"}</strong>
          <span>${row.checkpoint || "sin punto"} - ${row.scans} escaneos</span>
        </div>
      `).join("") || `<p class="empty">Sin operadores activos en los ultimos 15 minutos.</p>`}
    </div>
  `;
  $("#rejectionsList").innerHTML = status.recent_rejections.map((row) => `
    <div class="log rejected">
      <strong>${row.reason}</strong>
      <span>${row.first_name || ""} ${row.last_name || ""} - ${row.operator || "sin operador"} - ${new Date(row.created_at).toLocaleString()}</span>
    </div>
  `).join("") || `<p class="empty">Sin rechazos recientes.</p>`;
}

async function loadSummary() {
  if (!state.eventId) return;
  state.summary = await api(`/api/summary?event_id=${state.eventId}`);
  const visualSummary = await api(`/api/reports/visual-summary?event_id=${state.eventId}`);
  const participantMetrics = await api(`/api/participant-metrics?event_id=${state.eventId}`);
  const summary = state.summary;
  const acc = summary.accreditation || {};
  const reservations = Object.fromEntries(summary.reservations.map((row) => [row.status, Number(row.total || 0)]));
  const access = Object.fromEntries(summary.access.map((row) => [row.result, Number(row.total || 0)]));
  const activitiesOn = eventFeature("activities_enabled", true);
  const waitlistOn = eventFeature("waitlist_enabled", false);
  const reservationCards = activitiesOn ? `
      <div><strong>${reservations.confirmed || 0}</strong><span>Inscripciones confirmadas</span></div>
      ${waitlistOn ? `<div><strong>${reservations.waitlisted || 0}</strong><span>En espera</span></div>` : ""}
    ` : "";
  const activitySummary = activitiesOn ? `
    <div class="summary-columns">
      <div>
        <h3>Por actividad</h3>
        ${summary.by_activity.map((row) => `
          <div class="mini-row">
            <strong>${row.title}</strong>
            <span>${row.space_name} - ${Number(row.confirmed || 0)} confirmadas${waitlistOn ? ` - ${Number(row.waitlisted || 0)} espera` : ""}</span>
          </div>
        `).join("") || `<p class="empty">Sin actividades registradas.</p>`}
      </div>
    </div>
  ` : `<p class="empty">Este evento opera sin gestion de actividades.</p>`;
  $("#summaryStatus").innerHTML = `
    <div class="summary-grid">
      <div><strong>${Number(acc.active || 0)}</strong><span>Activas</span></div>
      <div><strong>${Number(acc.checked || 0)}</strong><span>Acreditadas</span></div>
      <div><strong>${Number(acc.pending || 0)}</strong><span>Pendientes</span></div>
      <div><strong>${Number(acc.cancelled || 0)}</strong><span>Canceladas</span></div>
      ${reservationCards}
      <div><strong>${access.granted || 0}</strong><span>Accesos OK</span></div>
      <div><strong>${access.rejected || 0}</strong><span>Rechazos</span></div>
      <div><strong>${Number(summary.attendance?.present || 0)}</strong><span>Asistencias</span></div>
      <div><strong>${Number(summary.attendance?.eligible || 0)}</strong><span>Elegibles certificado</span></div>
      <div><strong>${Number(summary.attendance?.average_percentage || 0)}%</strong><span>Participacion promedio</span></div>
    </div>
    ${activitySummary}
  `;
  $("#participantMetricsStatus").innerHTML = `
    <div><strong>${participantMetrics.registered || 0}</strong><span>Registrados</span></div>
    <div><strong>${participantMetrics.with_reservations || 0}</strong><span>Con inscripciones</span></div>
    <div><strong>${participantMetrics.with_agenda || 0}</strong><span>Con agenda</span></div>
    <div><strong>${participantMetrics.consent_email || 0}</strong><span>Email OK</span></div>
    <div><strong>${participantMetrics.consent_whatsapp || 0}</strong><span>WhatsApp OK</span></div>
    <div><strong>${participantMetrics.consent_both || 0}</strong><span>Ambos canales</span></div>
  `;
  const alerts = (visualSummary.operational_alerts || []).slice(0, 6);
  $("#operationalAlerts").innerHTML = alerts.map((row) => `
    <div class="mini-row alert-${row.level || "yellow"}">
      <strong>${row.title}</strong>
      <span>${row.message}</span>
    </div>
  `).join("") || `<p class="empty">Sin alertas operativas.</p>`;
}

async function loadMarketing() {
  if (!state.eventId) return;
  state.marketingDashboard = await api(`/api/marketing-dashboard?event_id=${state.eventId}`);
  const data = state.marketingDashboard;
  $("#marketingStatus").innerHTML = `
    <div class="summary-grid">
      <div><strong>${Number(data.totals?.visitors || 0)}</strong><span>Visitantes</span></div>
      <div><strong>${Number(data.totals?.registrations || 0)}</strong><span>Inscripciones</span></div>
      <div><strong>${Number(data.totals?.conversion_rate || 0)}%</strong><span>Conversion</span></div>
      <div><strong>${Number(data.totals?.abandonment || 0)}</strong><span>Abandono</span></div>
    </div>
    <div class="summary-columns">
      <div>
        <h3>Por origen</h3>
        ${(data.by_source || []).map((row) => `
          <div class="mini-row">
            <strong>${row.source || "sin origen"}</strong>
            <span>${Number(row.visitors || 0)} visitas - ${Number(row.registrations || 0)} inscripciones - ${Number(row.conversion_rate || 0)}%</span>
          </div>
        `).join("") || `<p class="empty">Sin datos de origen todavia.</p>`}
      </div>
      <div>
        <h3>Por dispositivo</h3>
        ${(data.by_device || []).map((row) => `
          <div class="mini-row">
            <strong>${row.device_type || "sin dispositivo"}</strong>
            <span>${Number(row.visitors || 0)} visitas - ${Number(row.registrations || 0)} inscripciones</span>
          </div>
        `).join("") || `<p class="empty">Sin datos de dispositivo todavia.</p>`}
      </div>
    </div>
    <h3>QR mas efectivos</h3>
    <div class="mini-list">
      ${(data.qr_sources || []).map((row) => `
        <div class="mini-row">
          <strong>${row.source_detail || row.source}</strong>
          <span>${Number(row.visitors || 0)} visitas - ${Number(row.registrations || 0)} inscripciones</span>
        </div>
      `).join("") || `<p class="empty">Sin QRs de captacion todavia.</p>`}
    </div>
  `;
}

async function loadReadiness() {
  if (!state.eventId) return;
  state.readiness = await api(`/api/readiness?event_id=${state.eventId}`);
  const readiness = state.readiness;
  $("#readinessStatus").innerHTML = `
    <div class="readiness-head ${readiness.ok ? "ok" : "warn"}">
      <strong>${readiness.ok ? "Listo para operar" : "Revisar antes de operar"}</strong>
      <span>Backup auto cada ${readiness.auto_backup_minutes} min - conserva ${readiness.backup_keep_last}</span>
    </div>
    <div class="readiness-list">
      ${readiness.checks.map((check) => `
        <div class="readiness-item ${check.ok ? "ok" : "warn"}">
          <strong>${check.label}</strong>
          <span>${check.detail}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function loadLogs() {
  const rows = await api(`/api/logs?event_id=${state.eventId || 0}`);
  $("#logs").innerHTML = rows.map((row) => `
    <div class="log ${row.result}">
      <strong>${row.reason}</strong>
      <span>${row.first_name || ""} ${row.last_name || ""} - ${row.operator || "sin operador"} - ${new Date(row.created_at).toLocaleString()}</span>
    </div>
  `).join("") || `<p class="empty">Todavia no hay accesos registrados.</p>`;
}

async function saveType(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = state.eventId;
  data.name = form.dataset.name;
  data.access_enabled = form.elements.access_enabled.checked;
  data.actor = state.currentUser;
  await api("/api/types", { method: "POST", body: JSON.stringify(data) });
  await Promise.all([loadTypes(), loadAccreditations(), loadReadiness(), loadAudit()]);
}

async function saveSpace(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  try {
    await api("/api/spaces", { method: "POST", body: JSON.stringify(data) });
    form.reset();
    form.elements.transition_minutes.value = 15;
    await loadAgenda();
  } catch (err) {
    $("#agendaAlert").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function saveActivity(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  try {
    await api("/api/activities", { method: "POST", body: JSON.stringify(data) });
    $("#agendaAlert").innerHTML = `<div class="panel success">Actividad agregada</div>`;
    form.reset();
    await Promise.all([loadAgenda(), loadAlerts(), loadReadiness()]);
  } catch (err) {
    $("#agendaAlert").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function saveReservation(event) {
  event.preventDefault();
  const data = formData(event.currentTarget);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  try {
    const result = await api("/api/reservations", { method: "POST", body: JSON.stringify(data) });
    $("#agendaAlert").innerHTML = `<div class="panel success">Inscripcion ${result.status === "confirmed" ? "confirmada" : "en lista de espera"}</div>`;
    await Promise.all([loadAgenda(), loadAlerts(), loadSummary(), loadReadiness(), loadAudit()]);
  } catch (err) {
    $("#agendaAlert").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function saveCapacityBag(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.id = form.dataset.id;
  data.actor = state.currentUser;
  data.public_visible = form.elements.public_visible.checked;
  data.public_registration = form.elements.public_registration.checked;
  data.reception_enabled = form.elements.reception_enabled.checked;
  data.release_enabled = true;
  try {
    await api("/api/capacity-bags", { method: "POST", body: JSON.stringify(data) });
    $("#agendaAlert").innerHTML = `<div class="panel success">Bolsa actualizada</div>`;
    await Promise.all([loadAgenda(), loadAlerts(), loadSummary(), loadReadiness(), loadAudit()]);
  } catch (err) {
    $("#agendaAlert").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function saveDisplayConfig(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  data.paused = form.elements.paused.checked;
  data.activity_ids = $$("#displayActivityPicker input:checked").map((input) => Number(input.value));
  try {
    await api("/api/public-display/config", { method: "POST", body: JSON.stringify(data) });
    await loadAgenda();
  } catch (err) {
    $("#alertsList").innerHTML = `<div class="alert danger">${err.message}</div>`;
  }
}

async function toggleDisplayItem(activityId) {
  await api("/api/public-display/item", {
    method: "POST",
    body: JSON.stringify({ event_id: state.eventId, activity_id: activityId, visible: true, actor: state.currentUser }),
  });
  $("#agendaAlert").innerHTML = `<div class="panel success">Actividad agregada a pantalla publica</div>`;
  await loadAgenda();
}

async function openActivityDetail(activityId) {
  const detail = await api(`/api/activity-detail?activity_id=${activityId}`);
  const panel = $("#activityDetailPanel");
  panel.classList.remove("hidden");
  $("#activityDetail").innerHTML = `
    <div class="detail-grid">
      <div><strong>${detail.activity.title}</strong><span>${detail.activity.space_name}</span></div>
      <div><strong>${new Date(detail.activity.starts_at).toLocaleString()}</strong><span>${new Date(detail.activity.ends_at).toLocaleTimeString()}</span></div>
      <div><strong>${detail.activity.capacity || "sin limite"}</strong><span>Capacidad fisica</span></div>
      <div><strong>${detail.availability.label}</strong><span>Disponibilidad publica</span></div>
      <div><strong>${Number(detail.stats.confirmed || 0)}</strong><span>Inscripciones</span></div>
      <div><strong>${Number(detail.stats.waitlisted || 0)}</strong><span>Lista espera</span></div>
      <div><strong>${Number(detail.attendance?.present || 0)}</strong><span>Presentes</span></div>
      <div><strong>${Number(detail.attendance?.absent || 0)}</strong><span>Ausentes</span></div>
      <div><strong>${Number(detail.attendance?.partial || 0)}</strong><span>Parciales</span></div>
      <div><strong>${Number(detail.attendance?.eligible || 0)}</strong><span>Elegibles</span></div>
      <div><strong>${Number(detail.attendance?.average_percentage || 0)}%</strong><span>Promedio</span></div>
      <div><strong>${Number(detail.access_window?.minutes_before || 0)} min</strong><span>QR habilita antes</span></div>
      <div><strong>${new Date(detail.access_window?.opens_at || detail.activity.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</strong><span>QR habilitado desde</span></div>
      <div><strong>${Number(detail.access_window?.early_attempts || 0)}</strong><span>Intentos anticipados</span></div>
      <div><strong>${Number(detail.access_window?.rejected || 0)}</strong><span>Rechazos actividad</span></div>
    </div>
    <h3>Asistencia</h3>
    <div class="mini-list">
      ${(detail.attendance_rows || []).map((row) => `
        <div class="mini-row attendance-admin-row">
          <div>
            <strong>${row.first_name} ${row.last_name}</strong>
            <span>${row.status} - ${Number(row.attendance_percentage || 0)}% - ${row.eligibility_status}</span>
          </div>
          <div class="row-actions">
            <button type="button" class="attendance-manual" data-id="${row.id}" data-status="Completa" data-percentage="100">Completa</button>
            <button type="button" class="attendance-manual" data-id="${row.id}" data-status="Presente" data-percentage="100">Presente</button>
            <button type="button" class="attendance-manual danger-button" data-id="${row.id}" data-status="Ausente" data-percentage="0">Ausente</button>
          </div>
        </div>
      `).join("") || `<p class="empty">Sin asistencias registradas.</p>`}
    </div>
    <h3>Bolsas</h3>
    <div class="mini-list">
      ${detail.bags.map((bag) => `
        <div class="mini-row">
          <strong>${bag.name}</strong>
          <span>${Number(bag.used || 0)}/${Number(bag.assigned_capacity || 0)} - ${bag.public_visible ? "publica" : "interna"}</span>
        </div>
      `).join("")}
    </div>
  `;
  $$(".attendance-manual").forEach((button) => button.addEventListener("click", () => updateAttendanceManual(button.dataset.id, button.dataset.status, button.dataset.percentage, activityId)));
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function updateAttendanceManual(id, status, percentage, activityId) {
  const reason = prompt(`Motivo de correccion: ${status}`) || "";
  await api("/api/attendance/manual", {
    method: "POST",
    body: JSON.stringify({ id, status, percentage, reason, actor: state.currentUser }),
  });
  $("#agendaAlert").innerHTML = `<div class="panel success">Asistencia corregida</div>`;
  await Promise.all([openActivityDetail(activityId), loadAgenda(), loadSummary(), loadAudit()]);
}

async function changeReservationStatus(id, status) {
  const label = status === "cancelled" ? "cancelar inscripcion" : "promover inscripcion";
  if (!confirm(`Confirmar ${label}`)) return;
  try {
    const result = await api("/api/reservations/status", {
      method: "POST",
      body: JSON.stringify({ id, status, actor: state.currentUser }),
    });
    const extra = result.promoted ? " y se promovio una inscripcion en espera" : "";
    $("#agendaAlert").innerHTML = `<div class="panel success">Inscripcion actualizada${extra}</div>`;
    await Promise.all([loadAgenda(), loadAlerts(), loadSummary(), loadReadiness(), loadAudit(), loadSystemStatus()]);
  } catch (err) {
    $("#agendaAlert").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function createEvent(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.status = "published";
  data.actor = state.currentUser;
  await api("/api/events", { method: "POST", body: JSON.stringify(data) });
  form.reset();
  await loadEvents();
}

async function prepareRealEvent(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  const notice = $("#prepareNotice");
  if (data.confirm !== "PREPARAR") {
    notice.innerHTML = `<div class="panel danger">Escribi PREPARAR para confirmar.</div>`;
    return;
  }
  if (!confirm("Esto crea backup y limpia datos operativos actuales. Confirmar preparacion.")) return;
  data.actor = state.currentUser;
  try {
    const result = await api("/api/prepare-event", { method: "POST", body: JSON.stringify(data) });
    notice.innerHTML = `<div class="panel success">Evento listo. Backup creado: ${result.backup}</div>`;
    form.reset();
    await loadEvents();
  } catch (err) {
    notice.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function createDemoReal(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  const notice = $("#prepareNotice");
  if (data.confirm !== "DEMO") {
    notice.innerHTML = `<div class="panel danger">Escribi DEMO para confirmar.</div>`;
    return;
  }
  if (!confirm("Esto crea backup, limpia datos operativos actuales y genera una demo completa. Confirmar demo.")) return;
  data.actor = state.currentUser;
  try {
    const result = await api("/api/demo-real", { method: "POST", body: JSON.stringify(data) });
    notice.innerHTML = `
      <div class="panel success">
        Demo real creada: ${result.participants} participantes, ${result.spaces} salas, ${result.activities} actividades.
        Pico operativo: ${result.peak?.entered || 0} ingresados, ${result.peak?.last_15_minutes || 0} ingresos en 15 min, ${result.peak?.active_terminals || 0} terminales activas.
        Backup previo: ${result.backup_before}. Backup demo: ${result.backup_after}.
      </div>
    `;
    form.elements.confirm.value = "DEMO";
    await loadEvents();
  } catch (err) {
    notice.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function createDemoLive10(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  const notice = $("#prepareNotice");
  if (data.confirm !== "LIVE10") {
    notice.innerHTML = `<div class="panel danger">Escribi LIVE10 para confirmar.</div>`;
    return;
  }
  data.actor = state.currentUser;
  try {
    const result = await api("/api/demo-live-10", { method: "POST", body: JSON.stringify(data) });
    notice.innerHTML = `
      <div class="panel success">
        <h3>Experiencia lista</h3>
        <p>Evento vacio con cupo para ${result.capacity} personas.</p>
        <a class="button" href="${result.landing_url}" target="_blank">Abrir landing para compartir</a>
      </div>
    `;
    await loadEvents();
    state.eventId = Number(result.event_id);
    $("#eventSelect").value = String(result.event_id);
  } catch (err) {
    notice.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function cloneEventFromTemplate(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.actor = state.currentUser;
  data.copy_all = form.elements.copy_all.checked;
  try {
    const result = await api("/api/events/clone", { method: "POST", body: JSON.stringify(data) });
    $("#templatesNotice").innerHTML = `<div class="panel success">Evento clonado. ID ${result.event_id}</div>`;
    form.reset();
    await loadEvents();
  } catch (err) {
    $("#templatesNotice").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function importEventStructure(event) {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const structure = JSON.parse(form.elements.structure_json.value || "{}");
    const result = await api("/api/event-structure/import", {
      method: "POST",
      body: JSON.stringify({ actor: state.currentUser, name: form.elements.name.value, structure }),
    });
    $("#templatesNotice").innerHTML = `<div class="panel success">Estructura importada. ID ${result.event_id}</div>`;
    form.reset();
    $("#structureImportFileName").textContent = "Ningun archivo seleccionado";
    await loadEvents();
  } catch (err) {
    $("#templatesNotice").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function loadStructureImportFile(event) {
  const file = event.target.files?.[0];
  const nameBox = $("#structureImportFileName");
  const field = $("#importStructureForm textarea[name='structure_json']");
  if (!file) {
    nameBox.textContent = "Ningun archivo seleccionado";
    field.value = "";
    return;
  }
  try {
    field.value = await file.text();
    JSON.parse(field.value);
    nameBox.textContent = `${file.name} - listo para importar`;
  } catch (err) {
    field.value = "";
    event.target.value = "";
    nameBox.textContent = "El archivo JSON no es valido";
    $("#templatesNotice").innerHTML = `<div class="panel danger">Selecciona un archivo JSON exportado por BITORA.</div>`;
  }
}

async function loadAgendaImportFile(event) {
  const file = event.target.files?.[0];
  const form = $("#importAgendaForm");
  const nameBox = $("#agendaImportFileName");
  form.elements.csv.value = "";
  form.elements.ics.value = "";
  if (!file) {
    nameBox.textContent = "Ningun archivo seleccionado";
    return;
  }
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!["csv", "ics"].includes(extension)) {
    event.target.value = "";
    nameBox.textContent = "Formato no compatible";
    $("#templatesNotice").innerHTML = `<div class="panel danger">La agenda debe estar en formato CSV o ICS.</div>`;
    return;
  }
  const content = await file.text();
  form.elements[extension].value = content;
  nameBox.textContent = `${file.name} - ${Math.max(1, Math.round(file.size / 1024))} KB`;
  $("#templatesNotice").innerHTML = "";
}

async function importAgenda(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.elements.csv.value && !form.elements.ics.value) {
    $("#templatesNotice").innerHTML = `<div class="panel danger">Selecciona un archivo CSV o ICS.</div>`;
    return;
  }
  const payload = {
    actor: state.currentUser,
    event_id: state.eventId,
    csv: form.elements.csv.value,
    ics: form.elements.ics.value,
  };
  try {
    if (event.submitter?.name === "preview") {
      const result = await api("/api/agenda/preview", { method: "POST", body: JSON.stringify(payload) });
      $("#templatesNotice").innerHTML = `<div class="panel ${result.errors?.length ? "warn" : "success"}">Previsualizacion: ${result.found} encontradas, ${result.valid} validas, ${result.conflicts} conflictos, ${result.errors.length} errores.</div>`;
    } else {
      const result = await api("/api/agenda/import", { method: "POST", body: JSON.stringify(payload) });
      const errors = result.errors?.length ? ` Errores: ${result.errors.length}` : "";
      $("#templatesNotice").innerHTML = `<div class="panel ${result.ok ? "success" : "danger"}">Agenda: ${result.created} creadas, ${result.updated} actualizadas.${errors}</div>`;
      if (result.ok) {
        form.reset();
        $("#agendaImportFileName").textContent = "Ningun archivo seleccionado";
      }
      await Promise.all([loadAgenda(), loadReadiness(), loadAudit()]);
    }
  } catch (err) {
    $("#templatesNotice").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function registerPerson(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  const result = await api("/api/register", { method: "POST", body: JSON.stringify(data) });
  $("#registerResult").innerHTML = `
    <div class="panel success">
      <h2>Credencial emitida</h2>
      <p>Token: <code>${result.token}</code></p>
      <a class="button" href="${result.portal_url}" target="_blank">Abrir portal del participante</a>
    </div>
  `;
  form.reset();
  await loadEvents();
}

async function validateAccess() {
  const token = $("#tokenInput").value.trim();
  const box = $("#accessResult");
  if (!token) {
    box.className = "access-result warn";
    box.textContent = "Ingresar token";
    return;
  }
  try {
    const result = await api("/api/validate", {
      method: "POST",
      body: JSON.stringify({
        token,
        operator: $("#operator").value || state.currentUser,
        checkpoint: $("#checkpoint").value,
        activity_id: $("#accessActivitySelect").value,
      }),
    });
    box.className = `access-result ${result.color}`;
    box.textContent = result.reason;
    $("#tokenInput").value = "";
    await loadEvents();
  } catch (err) {
    box.className = "access-result red";
    box.textContent = err.message;
  }
}

async function registerAttendanceExit() {
  const token = $("#tokenInput").value.trim();
  const activityId = $("#accessActivitySelect").value;
  const box = $("#accessResult");
  if (!token || !activityId) {
    box.className = "access-result warn";
    box.textContent = "Para egreso, ingresar token y elegir actividad";
    return;
  }
  try {
    const result = await api("/api/attendance/exit", {
      method: "POST",
      body: JSON.stringify({
        token,
        actor: $("#operator").value || state.currentUser,
        activity_id: activityId,
      }),
    });
    box.className = "access-result green";
    box.textContent = `Egreso registrado - ${result.percentage}% - ${result.eligibility_status}`;
    $("#tokenInput").value = "";
    await Promise.all([loadAgenda(), loadSummary(), loadAudit(), loadLogs()]);
  } catch (err) {
    box.className = "access-result red";
    box.textContent = err.message;
  }
}

async function manualCheckIn(token) {
  const notice = $("#receptionNotice");
  try {
    const result = await api("/api/validate", {
      method: "POST",
      body: JSON.stringify({
        token,
        operator: state.currentUser,
        checkpoint: "Acreditacion manual",
      }),
    });
    notice.innerHTML = `<div class="panel ${result.result === "granted" ? "success" : "danger"}">${result.reason}</div>`;
    await Promise.all([loadEvents(), loadAccreditations(), loadSystemStatus(), loadSummary(), loadReadiness(), loadLogs(), loadAudit()]);
  } catch (err) {
    notice.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

function openAccreditationEditor(id) {
  const row = state.accreditations.find((item) => Number(item.id) === Number(id));
  if (!row) return;
  const form = $("#editAccreditationForm");
  form.classList.remove("hidden");
  form.elements.id.value = row.id;
  form.elements.first_name.value = row.first_name || "";
  form.elements.last_name.value = row.last_name || "";
  form.elements.email.value = row.email || "";
  form.elements.phone.value = row.phone || "";
  form.elements.dni.value = row.dni || "";
  form.elements.company.value = row.company || "";
  form.elements.type.value = row.type || "General";
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function saveAccreditationEdit(event) {
  event.preventDefault();
  const data = formData(event.currentTarget);
  data.actor = state.currentUser;
  await api("/api/accreditations/update", { method: "POST", body: JSON.stringify(data) });
  event.currentTarget.classList.add("hidden");
  $("#receptionNotice").innerHTML = `<div class="panel success">Acreditacion actualizada</div>`;
  await Promise.all([loadAccreditations(), loadSummary(), loadReadiness(), loadAudit()]);
}

async function changeAccreditationStatus(id, status) {
  const label = status === "cancelled" ? "cancelar" : "reactivar";
  if (!confirm(`Confirmar ${label} acreditacion`)) return;
  await api("/api/accreditations/status", {
    method: "POST",
    body: JSON.stringify({ id, status, actor: state.currentUser }),
  });
  $("#receptionNotice").innerHTML = `<div class="panel success">Acreditacion ${status === "cancelled" ? "cancelada" : "reactivada"}</div>`;
  await Promise.all([loadAccreditations(), loadAgenda(), loadAlerts(), loadSummary(), loadReadiness(), loadAudit()]);
}

async function saveUser(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.actor = state.currentUser;
  await api("/api/users", { method: "POST", body: JSON.stringify(data) });
  form.reset();
  await Promise.all([loadUsers(), loadAudit()]);
}

async function sendDemoCommunication(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  data.template_code = form.dataset.templateCode || form.elements.type.value;
  data.type = form.elements.type.value;
  try {
    const result = await api("/api/communications/send", { method: "POST", body: JSON.stringify(data) });
    $("#communicationNotice").innerHTML = `<div class="panel success">Cola creada: ${result.queued}. Enviados/simulados: ${result.sent}. Omitidos: ${result.skipped}. Errores: ${result.errors}.</div>`;
    form.reset();
    await Promise.all([loadCommunications(), loadAudit()]);
  } catch (err) {
    $("#communicationNotice").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function sendTestEmail(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const notice = $("#emailTestNotice");
  try {
    const result = await api("/api/communications/email/test", {
      method: "POST",
      body: JSON.stringify({
        event_id: state.eventId,
        actor: state.currentUser,
        email: form.elements.email.value,
      }),
    });
    notice.innerHTML = `<div class="panel success">Email de prueba procesado. Enviados: ${Number(result.sent || 0)}.</div>`;
    await Promise.all([loadCommunications(), loadAudit()]);
  } catch (err) {
    notice.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function sendTestWhatsApp(event) {
  event.preventDefault();
  const data = formData(event.currentTarget);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  try {
    const result = await api("/api/communications/whatsapp/test", { method: "POST", body: JSON.stringify(data) });
    $("#whatsappTestNotice").innerHTML = `<div class="panel success">WhatsApp en cola. Job ${result.queue_id}.</div>`;
  } catch (err) {
    $("#whatsappTestNotice").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function testAssistant(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  try {
    const result = await api("/api/communications/assistant/message", { method: "POST", body: JSON.stringify(data) });
    $("#assistantTestResult").innerHTML = `<div class="panel success"><strong>${result.intent}</strong><p>${result.reply}</p></div>`;
    await loadCommunications();
  } catch (err) {
    $("#assistantTestResult").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

function parseCsv(text) {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) return [];
  const split = (line) => line.split(",").map((cell) => cell.trim());
  const headers = split(lines[0]).map((header) => header.toLowerCase());
  return lines.slice(1).map((line) => {
    const values = split(line);
    return Object.fromEntries(headers.map((header, index) => [header, values[index] || ""]));
  });
}

async function importAccreditations(event) {
  event.preventDefault();
  const rows = parseCsv($("#importCsv").value);
  const resultBox = $("#importResult");
  if (!rows.length) {
    resultBox.innerHTML = `<div class="panel danger">Pegá al menos una fila con encabezados.</div>`;
    return;
  }
  try {
    const result = await api("/api/import-accreditations", {
      method: "POST",
      body: JSON.stringify({ event_id: state.eventId, actor: state.currentUser, rows }),
    });
    resultBox.innerHTML = `
      <div class="panel success">
        Creados: ${result.created} - Existentes: ${result.existing} - Errores: ${result.errors}
      </div>
    `;
    await Promise.all([loadEvents(), loadAccreditations(), loadSummary(), loadReadiness(), loadAudit()]);
  } catch (err) {
    resultBox.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function loadImportFile(event) {
  const file = event.currentTarget.files[0];
  const nameBox = $("#importFileName");
  const resultBox = $("#importResult");
  if (!file) {
    nameBox.textContent = "Sin archivo seleccionado";
    return;
  }
  if (!file.name.toLowerCase().endsWith(".csv")) {
    event.currentTarget.value = "";
    nameBox.textContent = "Sin archivo seleccionado";
    resultBox.innerHTML = `<div class="panel danger">Selecciona un archivo CSV.</div>`;
    return;
  }
  try {
    $("#importCsv").value = await file.text();
    nameBox.textContent = `${file.name} cargado`;
    resultBox.innerHTML = `<div class="panel success">Archivo listo para importar.</div>`;
  } catch (err) {
    nameBox.textContent = "No se pudo leer el archivo";
    resultBox.innerHTML = `<div class="panel danger">No se pudo leer el CSV.</div>`;
  }
}

async function startCameraScan() {
  const box = $("#accessResult");
  if (!("BarcodeDetector" in window)) {
    box.className = "access-result warn";
    box.textContent = "Camara QR no soportada en este navegador";
    return;
  }
  try {
    state.cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    const video = $("#cameraPreview");
    video.srcObject = state.cameraStream;
    video.classList.add("active");
    await video.play();
    state.scanning = true;
    const detector = new BarcodeDetector({ formats: ["qr_code"] });
    const scan = async () => {
      if (!state.scanning) return;
      const codes = await detector.detect(video);
      if (codes.length) {
        $("#tokenInput").value = codes[0].rawValue;
        stopCameraScan();
        await validateAccess();
        return;
      }
      requestAnimationFrame(scan);
    };
    scan();
  } catch (err) {
    box.className = "access-result red";
    box.textContent = "No se pudo abrir la camara";
  }
}

function stopCameraScan() {
  state.scanning = false;
  if (state.cameraStream) {
    state.cameraStream.getTracks().forEach((track) => track.stop());
    state.cameraStream = null;
  }
  $("#cameraPreview").classList.remove("active");
}

document.addEventListener("DOMContentLoaded", async () => {
  organizeReportAndDiagnosticViews();
  $$("nav button").forEach((button) => button.addEventListener("click", () => {
    setView(button.dataset.view);
    if (button.dataset.view === "diagnostics") loadDiagnostics();
    if (button.dataset.view === "simulator") loadSimulator();
    if (button.dataset.view === "reports") loadVisualization();
    const url = button.dataset.view === "dashboard" ? `${location.pathname}${location.search}` : `#${button.dataset.view}`;
    history.replaceState(null, "", url);
  }));
  $$("[data-view-target]").forEach((button) => button.addEventListener("click", () => {
    const target = button.dataset.viewTarget;
    setView(target);
    history.replaceState(null, "", target === "dashboard" ? `${location.pathname}${location.search}` : `#${target}`);
  }));
  $("#eventSelect").addEventListener("change", async (event) => {
    state.eventId = Number(event.target.value);
    updateMetrics();
    await Promise.all([loadTypes(), loadAccreditations(), loadAgenda(), loadAlerts(), loadSystemStatus(), loadNetworkInfo(), loadSummary(), loadMarketing(), loadReadiness(), loadAudit(), loadCommunications(), loadDemoReal(), loadLogs()]);
  });
  $("#currentUserSelect").addEventListener("change", (event) => {
    state.currentUser = event.target.value;
    $("#operator").value = state.currentUser;
  });
  $("#eventForm").addEventListener("submit", createEvent);
  $("#prepareEventForm").addEventListener("submit", prepareRealEvent);
  $("#demoRealForm").addEventListener("submit", createDemoReal);
  $("#demoLive10Form")?.addEventListener("submit", createDemoLive10);
  $("#cloneEventForm")?.addEventListener("submit", cloneEventFromTemplate);
  $("#importStructureForm").addEventListener("submit", importEventStructure);
  $("#importAgendaForm").addEventListener("submit", importAgenda);
  $("#structureImportFile")?.addEventListener("change", loadStructureImportFile);
  $("#agendaImportFile")?.addEventListener("change", loadAgendaImportFile);
  $("#controlRoomRefresh").addEventListener("change", updateControlRoomLink);
  $("#controlRoomDark").addEventListener("change", updateControlRoomLink);
  $("#controlRoomCompact").addEventListener("change", updateControlRoomLink);
  $("#controlRoomRotate").addEventListener("change", updateControlRoomLink);
  $("#controlRoomMaxRooms").addEventListener("input", updateControlRoomLink);
  $("#controlRoomMaxAlerts").addEventListener("input", updateControlRoomLink);
  $$(".visual-block-picker input").forEach((input) => input.addEventListener("change", updateControlRoomLink));
  $("#registerForm").addEventListener("submit", registerPerson);
  $("#editAccreditationForm").addEventListener("submit", saveAccreditationEdit);
  $("#importForm").addEventListener("submit", importAccreditations);
  $("#importFile").addEventListener("change", loadImportFile);
  $("#landingImageForm")?.addEventListener("submit", saveLandingImage);
  $("#waitingRoomConfigForm")?.addEventListener("submit", saveWaitingRoomConfig);
  $("#deleteLandingImageBtn")?.addEventListener("click", deleteLandingImage);
  $("#userForm").addEventListener("submit", saveUser);
  $("#communicationForm").addEventListener("submit", sendDemoCommunication);
  $("#emailTestForm")?.addEventListener("submit", sendTestEmail);
  $("#whatsappTestForm")?.addEventListener("submit", sendTestWhatsApp);
  $("#assistantTestForm").addEventListener("submit", testAssistant);
  $("#spaceForm").addEventListener("submit", saveSpace);
  $("#activityForm").addEventListener("submit", saveActivity);
  $("#reservationForm")?.addEventListener("submit", saveReservation);
  $("#displayConfigForm").addEventListener("submit", saveDisplayConfig);
  $("#refreshBtn").addEventListener("click", loadEvents);
  $("#logoutBtn").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST", body: JSON.stringify({}) });
    location.href = "/login.html";
  });
  $("#refreshDiagnosticsBtn")?.addEventListener("click", loadDiagnostics);
  $("#refreshVisualizationBtn")?.addEventListener("click", () => loadVisualization(true));
  $("#visualizationDashboard")?.addEventListener("change", () => loadVisualization());
  $("#visualizationPeriod")?.addEventListener("change", () => loadVisualization());
  $("#visualizationHeatmap")?.addEventListener("change", renderVisualization);
  $("#visualizationSeries")?.addEventListener("change", renderVisualization);
  $("#saveVisualizationLayoutBtn")?.addEventListener("click", saveVisualizationLayout);
  $("#diagnosticsLogFilter")?.addEventListener("change", renderDiagnosticsLogs);
  $$("[data-simulator-action]").forEach((button) => button.addEventListener("click", () => controlSimulator(button.dataset.simulatorAction)));
  $("#printFilteredBtn").addEventListener("click", printFilteredCredentials);
  $("#searchInput").addEventListener("input", () => loadAccreditations());
  $("#statusFilter").addEventListener("change", () => loadAccreditations());
  $("#typeFilter").addEventListener("change", () => loadAccreditations());
  $("#quickReceptionSearch")?.addEventListener("input", () => loadQuickReception());
  $("#quickReceptionToken")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") quickValidateReceptionToken();
  });
  $("#quickReceptionValidate")?.addEventListener("click", quickValidateReceptionToken);
  $("#validateBtn").addEventListener("click", validateAccess);
  $("#attendanceExitBtn").addEventListener("click", registerAttendanceExit);
  $("#cameraBtn").addEventListener("click", startCameraScan);
  $("#tokenInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") validateAccess();
  });
  await loadEvents();
  let initialView = new URLSearchParams(location.search).get("view") || location.hash.replace("#", "");
  if (initialView === "visualization") initialView = "reports";
  if (initialView && document.getElementById(initialView)?.classList.contains("view")) {
    setView(initialView);
    if (initialView === "diagnostics") await loadDiagnostics();
    if (initialView === "simulator") await loadSimulator();
    if (initialView === "reports") await loadVisualization();
  }
});
