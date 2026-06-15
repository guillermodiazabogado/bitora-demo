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
  demoReal: null,
  currentUser: "Admin",
  eventId: null,
  cameraStream: null,
  scanning: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

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
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  $$("nav button").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
}

async function loadEvents() {
  await loadAuth();
  await loadUsers();
  state.events = await api("/api/events");
  const select = $("#eventSelect");
  select.innerHTML = state.events.map((event) => `<option value="${event.id}">${event.name}</option>`).join("");
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
  } else {
    $("#logoutBtn").classList.add("hidden");
  }
}

function currentEvent() {
  return state.events.find((event) => Number(event.id) === Number(state.eventId));
}

function updateMetrics() {
  const event = currentEvent();
  const total = Number(event?.accreditation_count || 0);
  const checked = Number(event?.checked_in_count || 0);
  $("#mTotal").textContent = total;
  $("#mIn").textContent = checked;
  $("#mPending").textContent = Math.max(total - checked, 0);
  $("#exportLink").href = state.eventId ? `/api/export.csv?event_id=${state.eventId}` : "#";
  $("#exportJsonLink").href = state.eventId ? `/api/export.json?event_id=${state.eventId}` : "#";
  $("#exportReservationsLink").href = state.eventId ? `/api/reservations.csv?event_id=${state.eventId}` : "#";
  $("#exportAttendancesLink").href = state.eventId ? `/api/attendances.csv?event_id=${state.eventId}` : "#";
  $("#exportCertificatesLink").href = state.eventId ? `/api/certificate-eligibility.csv?event_id=${state.eventId}&status=eligible` : "#";
  $("#exportCaptationLink").href = state.eventId ? `/api/captation.csv?event_id=${state.eventId}` : "#";
  $("#publicEventLink").href = state.eventId ? `/e.html?event_id=${state.eventId}` : "#";
  $("#publicDisplayLink").href = state.eventId ? `/display.html?event_id=${state.eventId}` : "#";
  $("#backupLink").href = state.eventId ? `/api/backup?event_id=${state.eventId}` : "/api/backup";
}

async function loadAccreditations() {
  if (!state.eventId) return;
  const q = encodeURIComponent($("#searchInput")?.value || "");
  const rows = filterAccreditations(await api(`/api/accreditations?event_id=${state.eventId}&q=${q}`));
  state.accreditations = await api(`/api/accreditations?event_id=${state.eventId}`);
  $("#accreditations").innerHTML = rows.map((row) => `
    <article class="row">
      <div>
        <strong>${row.first_name} ${row.last_name}</strong>
        <span>${row.company || row.email} - ${row.email}</span>
      </div>
      <code>${row.token}</code>
      <span class="pill">${row.type}</span>
      <span class="status ${row.checked_in_at ? "ok" : ""}">${accreditationStatusLabel(row)}</span>
      <div class="row-actions">
        <a class="button ghost" href="/p.html?token=${row.token}" target="_blank">Credencial</a>
        <button type="button" class="print-one" data-token="${row.token}">Imprimir</button>
        <button type="button" class="certificate-one" data-token="${row.token}">Certificado</button>
        <button type="button" class="edit-accreditation" data-id="${row.id}">Editar</button>
        <button type="button" class="manual-checkin" data-token="${row.token}">Acreditar</button>
        ${row.status === "cancelled"
          ? `<button type="button" class="status-accreditation" data-id="${row.id}" data-status="active">Reactivar</button>`
          : `<button type="button" class="status-accreditation danger-button" data-id="${row.id}" data-status="cancelled">Cancelar</button>`}
        ${row.phone ? `<a class="button ghost" href="${whatsappLink(row)}" target="_blank">WhatsApp</a>` : ""}
      </div>
    </article>
  `).join("") || `<p class="empty">No hay acreditados para mostrar.</p>`;
  $$(".manual-checkin").forEach((button) => button.addEventListener("click", () => manualCheckIn(button.dataset.token)));
  $$(".print-one").forEach((button) => button.addEventListener("click", () => printOneCredential(button.dataset.token)));
  $$(".certificate-one").forEach((button) => button.addEventListener("click", () => printManualCertificate(button.dataset.token)));
  $$(".edit-accreditation").forEach((button) => button.addEventListener("click", () => openAccreditationEditor(button.dataset.id)));
  $$(".status-accreditation").forEach((button) => button.addEventListener("click", () => changeAccreditationStatus(button.dataset.id, button.dataset.status)));
  renderReservationSelectors();
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

function printManualCertificate(token) {
  window.open(`/api/certificate.pdf?token=${encodeURIComponent(token)}&manual=1`, "_blank");
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
  $("#communicationStats").innerHTML = `
    <div><strong>${Number(stats.participants || 0)}</strong><span>Participantes</span></div>
    <div><strong>${Number(stats.with_email || 0)}</strong><span>Con email</span></div>
    <div><strong>${Number(stats.with_whatsapp || 0)}</strong><span>Con WhatsApp</span></div>
    <div><strong>${Number(stats.with_both || 0)}</strong><span>Con ambos</span></div>
    <div><strong>${Number(stats.with_consent || 0)}</strong><span>Con consentimiento</span></div>
  `;
  $("#communicationTemplates").innerHTML = state.communications.templates.map((row) => `
    <button type="button" class="mini-row template-pick" data-type="${row.tipo}" data-subject="${row.asunto}" data-content="${row.contenido}">
      <strong>${row.name}</strong>
      <span>${row.tipo}</span>
    </button>
  `).join("") || `<p class="empty">Sin plantillas.</p>`;
  $("#communicationTypeSelect").innerHTML = state.communications.templates.map((row) => (
    `<option value="${row.tipo}">${row.name}</option>`
  )).join("") || `<option value="aviso operativo">Aviso operativo</option>`;
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
  }));
}

async function loadDemoReal() {
  if (!state.eventId) return;
  state.demoReal = await api(`/api/demo-real?event_id=${state.eventId}`);
  const panel = $("#demoRealPanel");
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
        <a class="button ghost" href="${row.portal_url}#actividades" target="_blank">Reservas</a>
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
  state.displayConfig = display.config;
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
      <a class="button ghost" href="/api/reservations.csv?event_id=${state.eventId}&activity_id=${row.id}">Reservas CSV</a>
      <a class="button ghost" href="/api/attendances.csv?event_id=${state.eventId}&activity_id=${row.id}">Asistencias CSV</a>
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
  const confirmed = Number(row.confirmed_count || 0);
  const waitlist = Number(row.waitlist_count || 0);
  const capacity = Number(row.capacity || 0);
  const base = capacity ? `${confirmed}/${capacity}` : `${confirmed}/sin limite`;
  return waitlist ? `${base} + ${waitlist} espera` : base;
}

function renderDisplayConfig() {
  if (!state.displayConfig) return;
  $("#displayMode").value = state.displayConfig.mode || "airport";
  $("#displayRefresh").value = state.displayConfig.refresh_seconds || 10;
  $("#displayPaused").checked = Number(state.displayConfig.paused || 0) === 1;
  $("#displayMessageInput").value = state.displayConfig.message || "";
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
  $("#reservationsList").innerHTML = state.reservations.map((row) => `
    <article class="reservation-row ${row.status}">
      <strong>${row.first_name} ${row.last_name}</strong>
      <span>${row.activity_title} - ${row.space_name}</span>
      <span class="pill">${reservationStatusLabel(row.status)}</span>
      <div class="reservation-actions">
        ${row.status === "waitlisted" ? `<button type="button" class="reservation-status" data-id="${row.id}" data-status="confirmed">Promover</button>` : ""}
        ${row.status !== "cancelled" ? `<button type="button" class="reservation-status danger-button" data-id="${row.id}" data-status="cancelled">Cancelar</button>` : ""}
      </div>
    </article>
  `).join("") || `<p class="empty">Todavia no hay reservas.</p>`;
  $$(".reservation-status").forEach((button) => (
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
  const participantMetrics = await api(`/api/participant-metrics?event_id=${state.eventId}`);
  const summary = state.summary;
  const acc = summary.accreditation || {};
  const reservations = Object.fromEntries(summary.reservations.map((row) => [row.status, Number(row.total || 0)]));
  const access = Object.fromEntries(summary.access.map((row) => [row.result, Number(row.total || 0)]));
  $("#summaryStatus").innerHTML = `
    <div class="summary-grid">
      <div><strong>${Number(acc.active || 0)}</strong><span>Activas</span></div>
      <div><strong>${Number(acc.checked || 0)}</strong><span>Acreditadas</span></div>
      <div><strong>${Number(acc.pending || 0)}</strong><span>Pendientes</span></div>
      <div><strong>${Number(acc.cancelled || 0)}</strong><span>Canceladas</span></div>
      <div><strong>${reservations.confirmed || 0}</strong><span>Reservas confirmadas</span></div>
      <div><strong>${reservations.waitlisted || 0}</strong><span>En espera</span></div>
      <div><strong>${access.granted || 0}</strong><span>Accesos OK</span></div>
      <div><strong>${access.rejected || 0}</strong><span>Rechazos</span></div>
      <div><strong>${Number(summary.attendance?.present || 0)}</strong><span>Asistencias</span></div>
      <div><strong>${Number(summary.attendance?.eligible || 0)}</strong><span>Elegibles certificado</span></div>
      <div><strong>${Number(summary.attendance?.average_percentage || 0)}%</strong><span>Participacion promedio</span></div>
    </div>
    <div class="summary-columns">
      <div>
        <h3>Por tipo</h3>
        ${summary.by_type.map((row) => `
          <div class="mini-row">
            <strong>${row.type}</strong>
            <span>${Number(row.checked || 0)}/${Number(row.active || 0)} acreditadas - ${Number(row.cancelled || 0)} canceladas</span>
          </div>
        `).join("") || `<p class="empty">Sin tipos registrados.</p>`}
      </div>
      <div>
        <h3>Por actividad</h3>
        ${summary.by_activity.map((row) => `
          <div class="mini-row">
            <strong>${row.title}</strong>
            <span>${row.space_name} - ${Number(row.confirmed || 0)} confirmadas - ${Number(row.waitlisted || 0)} espera</span>
          </div>
        `).join("") || `<p class="empty">Sin actividades registradas.</p>`}
      </div>
    </div>
  `;
  $("#participantMetricsStatus").innerHTML = `
    <div><strong>${participantMetrics.registered || 0}</strong><span>Registrados</span></div>
    <div><strong>${participantMetrics.with_reservations || 0}</strong><span>Con reservas</span></div>
    <div><strong>${participantMetrics.with_agenda || 0}</strong><span>Con agenda</span></div>
    <div><strong>${participantMetrics.consent_email || 0}</strong><span>Email OK</span></div>
    <div><strong>${participantMetrics.consent_whatsapp || 0}</strong><span>WhatsApp OK</span></div>
    <div><strong>${participantMetrics.consent_both || 0}</strong><span>Ambos canales</span></div>
  `;
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
    $("#agendaAlert").innerHTML = `<div class="panel success">Reserva ${result.status === "confirmed" ? "confirmada" : "en lista de espera"}</div>`;
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
      <div><strong>${Number(detail.stats.confirmed || 0)}</strong><span>Reservas</span></div>
      <div><strong>${Number(detail.stats.waitlisted || 0)}</strong><span>Lista espera</span></div>
      <div><strong>${Number(detail.attendance?.present || 0)}</strong><span>Presentes</span></div>
      <div><strong>${Number(detail.attendance?.absent || 0)}</strong><span>Ausentes</span></div>
      <div><strong>${Number(detail.attendance?.partial || 0)}</strong><span>Parciales</span></div>
      <div><strong>${Number(detail.attendance?.eligible || 0)}</strong><span>Elegibles</span></div>
      <div><strong>${Number(detail.attendance?.average_percentage || 0)}%</strong><span>Promedio</span></div>
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
  const label = status === "cancelled" ? "cancelar reserva" : "promover reserva";
  if (!confirm(`Confirmar ${label}`)) return;
  try {
    const result = await api("/api/reservations/status", {
      method: "POST",
      body: JSON.stringify({ id, status, actor: state.currentUser }),
    });
    const extra = result.promoted ? " y se promovio una reserva en espera" : "";
    $("#agendaAlert").innerHTML = `<div class="panel success">Reserva actualizada${extra}</div>`;
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
        Backup previo: ${result.backup_before}. Backup demo: ${result.backup_after}.
      </div>
    `;
    form.reset();
    await loadEvents();
  } catch (err) {
    notice.innerHTML = `<div class="panel danger">${err.message}</div>`;
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
  try {
    const result = await api("/api/communications/send", { method: "POST", body: JSON.stringify(data) });
    $("#communicationNotice").innerHTML = `<div class="panel success">Envios registrados: ${result.sent}. Omitidos por consentimiento: ${result.skipped}.</div>`;
    form.reset();
    await Promise.all([loadCommunications(), loadAudit()]);
  } catch (err) {
    $("#communicationNotice").innerHTML = `<div class="panel danger">${err.message}</div>`;
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
  $$("nav button").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
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
  $("#registerForm").addEventListener("submit", registerPerson);
  $("#editAccreditationForm").addEventListener("submit", saveAccreditationEdit);
  $("#importForm").addEventListener("submit", importAccreditations);
  $("#importFile").addEventListener("change", loadImportFile);
  $("#userForm").addEventListener("submit", saveUser);
  $("#communicationForm").addEventListener("submit", sendDemoCommunication);
  $("#spaceForm").addEventListener("submit", saveSpace);
  $("#activityForm").addEventListener("submit", saveActivity);
  $("#reservationForm").addEventListener("submit", saveReservation);
  $("#displayConfigForm").addEventListener("submit", saveDisplayConfig);
  $("#refreshBtn").addEventListener("click", loadEvents);
  $("#logoutBtn").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST", body: JSON.stringify({}) });
    location.href = "/login.html";
  });
  $("#printFilteredBtn").addEventListener("click", printFilteredCredentials);
  $("#searchInput").addEventListener("input", () => loadAccreditations());
  $("#statusFilter").addEventListener("change", () => loadAccreditations());
  $("#typeFilter").addEventListener("change", () => loadAccreditations());
  $("#validateBtn").addEventListener("click", validateAccess);
  $("#attendanceExitBtn").addEventListener("click", registerAttendanceExit);
  $("#cameraBtn").addEventListener("click", startCameraScan);
  $("#tokenInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") validateAccess();
  });
  await loadEvents();
});
