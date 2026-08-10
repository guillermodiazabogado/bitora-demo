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
  eventUsers: [],
  permissions: null,
  selectedUserId: null,
  permissionDraft: null,
  permissionChanges: {},
  audit: [],
  communications: null,
  googleOAuth: null,
  diagnostics: null,
  simulator: null,
  visualization: null,
  visualizationLayouts: [],
  demoReal: null,
  eventRestore: null,
  appConfig: null,
  currentUser: "Admin",
  eventId: null,
  cameraStream: null,
  scanning: false,
};

const MODULE_LABELS = {
  owner: "Mis eventos",
  organizations: "Organizaciones",
  dashboard: "Panel",
  home: "Inicio",
  register: "Inscribir",
  reception: "Recepcion",
  agenda: "Agenda",
  access: "Acceso QR",
  configure: "Configurar Evento",
  users: "Usuarios y Permisos",
  reports: "Reportes",
  communications: "Comunicaciones",
  certificates: "Certificados",
  surveys: "Encuestas",
  speakers: "Speakers",
  zones: "Zonas",
  history: "Historial",
  operations: "Operations Center",
  analytics: "Analytics",
  audit: "Auditoria",
  diagnostics: "Diagnostico Tecnico",
  simulator: "Simulador Vivo",
};

const ACTION_LABELS = {
  create_event: "Crear eventos",
  manage_users: "Administrar usuarios",
  manage_event_team: "Asignar equipo",
  configure_event: "Configurar evento",
  import_export: "Importar / exportar",
  communicate: "Comunicaciones",
  manual_accredit: "Recepcion y acreditacion",
  register_participants: "Inscribir participantes",
  scan_qr: "Validar QR",
  view_reports: "Ver reportes",
  view_audit: "Ver auditoria",
  technical_diagnostics: "Diagnostico tecnico",
  "communications.view": "Comunicaciones: ver centro",
  "communications.create": "Comunicaciones: crear borrador",
  "communications.edit": "Comunicaciones: editar borrador",
  "communications.preview": "Comunicaciones: previsualizar",
  "communications.select_audience": "Comunicaciones: elegir audiencia",
  "communications.send": "Comunicaciones: enviar masivo",
  "communications.schedule": "Comunicaciones: programar",
  "communications.pause": "Comunicaciones: pausar cola",
  "communications.resume": "Comunicaciones: reanudar cola",
  "communications.cancel": "Comunicaciones: cancelar pendientes",
  "communications.resend_individual": "Comunicaciones: reenviar individual",
  "communications.view_history": "Comunicaciones: ver historial",
  "communications.view_metrics": "Comunicaciones: ver metricas",
  "communications.manage_templates": "Comunicaciones: gestionar plantillas",
  "communications.approve_templates": "Comunicaciones: aprobar plantillas",
  "communications.manage_providers": "Comunicaciones: configurar proveedores",
  "communications.view_technical_logs": "Comunicaciones: logs tecnicos",
  "communications.retry_failed": "Comunicaciones: reintentar fallidos",
  "communications.export": "Comunicaciones: exportar",
  "communications.view_personal_data": "Comunicaciones: ver datos personales",
  "communications.manage_consent": "Comunicaciones: gestionar consentimiento",
  "backups.view": "Backups: ver estado",
  "backups.create_event": "Backups: crear backup del evento",
  "backups.create_full": "Backups: crear backup completo",
  "backups.download": "Backups: descargar",
  "backups.verify": "Backups: verificar integridad",
  "backups.restore_event": "Backups: restaurar evento",
  "backups.restore_event_overwrite": "Backups: sobrescribir evento",
  "backups.restore_full": "Backups: restaurar sistema",
  "backups.manage_schedule": "Backups: programacion automatica",
  "backups.manage_retention": "Backups: retencion",
  "backups.view_logs": "Backups: ver logs",
  "backups.view_manifest": "Backups: ver manifiesto",
  "organizations.view": "Organizaciones: ver",
  "organizations.edit": "Organizaciones: crear / editar",
  "organizations.manage_users": "Organizaciones: usuarios",
  "integrations.view": "Integraciones: ver",
  "integrations.create": "Integraciones: crear",
  "integrations.edit": "Integraciones: editar",
  "integrations.test": "Integraciones: probar conexion",
  "integrations.rotate": "Integraciones: rotar secretos",
  "integrations.disable": "Integraciones: deshabilitar",
  "integrations.google_connect": "Google: conectar",
  "integrations.google_disconnect": "Google: desconectar",
  "integrations.google_refresh": "Google: renovar token",
  "event_integrations.view": "Evento: ver integraciones",
  "event_integrations.assign": "Evento: asignar integraciones",
  "communications.configure": "Comunicaciones: configurar canal",
  "communications.send_test": "Comunicaciones: envio de prueba",
};

const PRODUCER_HOME_MODULES = [
  {
    key: "dashboard",
    title: "Panel de Control",
    description: "Resumen general del evento, indicadores clave y actividad en tiempo real.",
    icon: "PC",
    tone: "purple",
    view: "dashboard",
    metric: () => `${Number(currentEvent()?.checked_in_count || 0)} acreditados`,
  },
  {
    key: "register",
    title: "Inscripciones",
    description: "Gestion de participantes, estados de inscripcion y datos de registro.",
    icon: "IN",
    tone: "green",
    view: "register",
    feature: "registration",
    metric: () => `${Number(currentEvent()?.accreditation_count || 0)} inscriptos`,
  },
  {
    key: "reception",
    title: "Recepcion",
    description: "Acreditacion de participantes y entrega de credenciales.",
    icon: "RC",
    tone: "blue",
    view: "reception",
    feature: "reception",
    metric: () => `${state.accreditations.filter((row) => row.status === "checked_in").length} acreditados`,
  },
  {
    key: "access",
    title: "Acceso",
    description: "Control de acceso con QR, validacion y monitoreo en tiempo real.",
    icon: "QR",
    tone: "teal",
    view: "access",
    feature: "access",
    metric: () => "En vivo",
  },
  {
    key: "attendance",
    title: "Asistencia",
    description: "Control de asistencia a actividades y sesiones del evento.",
    icon: "AS",
    tone: "orange",
    route: "/attendance-closure.html",
    action: "attendance.read",
    feature: "agenda",
    featureFlag: "attendance_closure_eligibility_v4_enabled",
    metric: () => "Control activo",
  },
  {
    key: "agenda",
    title: "Actividades",
    description: "Gestion de actividades, salas, horarios y cupos disponibles.",
    icon: "AG",
    tone: "indigo",
    view: "agenda",
    feature: "agenda",
    metric: () => `${state.activities.length} actividades`,
  },
  {
    key: "speakers",
    title: "Speakers",
    description: "Administracion de expositores y su participacion en el evento.",
    icon: "SP",
    tone: "yellow",
    route: "/speakers-v4.html",
    permissionModule: "speakers",
    action: "speakers.read",
    featureFlag: "speakers_v4_enabled",
    metric: () => "Modulo habilitado",
  },
  {
    key: "certificates",
    title: "Certificados",
    description: "Generacion y gestion de certificados para participantes.",
    icon: "CE",
    tone: "cyan",
    route: "/certificates-v4.html",
    permissionModule: "certificates",
    action: "certificates.read",
    featureFlag: "certificates_v4_enabled",
    metric: () => "Elegibilidad",
  },
  {
    key: "surveys",
    title: "Encuestas",
    description: "Creacion y analisis de encuestas de satisfaccion.",
    icon: "EN",
    tone: "pink",
    route: "/surveys-v4.html",
    permissionModule: "surveys",
    action: "surveys.read",
    featureFlag: "surveys_v4_enabled",
    metric: () => "Modulo habilitado",
  },
  {
    key: "communications",
    title: "Comunicaciones",
    description: "Envio de comunicaciones y campanas a participantes.",
    icon: "CO",
    tone: "red",
    view: "communications",
    permissionModule: "communications",
    action: "communications.view",
    featureFlag: "communications_automation_v4_enabled",
    metric: () => "Safe Mode",
  },
  {
    key: "operations",
    title: "Operations Center",
    description: "Monitoreo avanzado del evento y gestion operativa.",
    icon: "OP",
    tone: "mint",
    route: "/operations-center-v4.html",
    action: "operations_center.read",
    featureFlag: "operations_center_v4_enabled",
    metric: () => "Todo operativo",
  },
  {
    key: "analytics",
    title: "Analytics",
    description: "Reportes, metricas y analisis del desempeno del evento.",
    icon: "AN",
    tone: "blue",
    route: "/analytics-v4.html",
    action: "analytics.read",
    featureFlag: "analytics_v4_enabled",
    fallbackView: "reports",
    metric: () => "Ver reportes",
  },
];

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
  state.appConfig = config || {};
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

function updateProducerHomeReturn(name) {
  const button = $("#producerHomeReturnBtn");
  if (!button) return;
  const show = producerHomeAllowed() && name !== "home";
  button.classList.toggle("hidden", !show);
}

function setView(name) {
  if (name === "visualization") name = "reports";
  if (state.authUser?.must_change_password && name !== "passwordChange") {
    name = "passwordChange";
  }
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  $$("nav button").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  updateProducerHomeReturn(name);
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
  select.innerHTML = eventOptionsHtml();
  const requestedEventId = Number(new URLSearchParams(location.search).get("event_id") || 0);
  if (previousEventId && state.events.some((event) => Number(event.id) === Number(previousEventId))) {
    select.value = String(previousEventId);
  } else if (requestedEventId && state.events.some((event) => Number(event.id) === requestedEventId)) {
    select.value = String(requestedEventId);
  }
  if ($("#cloneEventSelect")) {
    $("#cloneEventSelect").innerHTML = state.events.map((event) => `<option value="${event.id}">${event.name}</option>`).join("");
  }
  state.eventId = Number(select.value || state.events[0]?.id || 0);
  syncEventSelectors();
  await loadPermissions();
  updateMetrics();
  renderOwnerDashboard();
  if (!state.eventId) return;
  await reloadCurrentEventData();
}

function eventOptionsHtml() {
  return state.events.map((event) => `<option value="${event.id}">${escapeHtml(event.name)}</option>`).join("");
}

function syncEventSelectors() {
  ["eventSelect", "usersEventSelect", "producerHomeEventSelect"].forEach((id) => {
    const select = $(`#${id}`);
    if (!select) return;
    if (select.options.length !== state.events.length) {
      select.innerHTML = eventOptionsHtml();
    }
    select.value = String(state.eventId || "");
  });
}

async function selectActiveEvent(eventId) {
  state.eventId = Number(eventId || 0);
  syncEventSelectors();
  await loadPermissions();
  updateMetrics();
  renderOwnerDashboard();
  await reloadCurrentEventData();
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

function effectiveRole() {
  return state.permissions?.effective_role || state.authUser?.role || "Visualizador";
}

function permissionsFor(role = effectiveRole()) {
  return state.permissions?.matrix?.[role] || { modules: [], actions: [] };
}

function canSeeModule(module) {
  return permissionsFor().modules.includes(module);
}

function canDo(action) {
  return permissionsFor().actions.includes(action);
}

function producerHomeAllowed() {
  return Boolean(state.eventId && effectiveRole() === "Productor" && canSeeModule("dashboard"));
}

function producerDefaultView() {
  return state.authUser?.role === "Productor" && producerHomeAllowed() ? "home" : "";
}

function updateProducerChrome() {
  document.body.classList.toggle("producer-mode", producerHomeAllowed());
}

function moduleFeatureEnabled(module) {
  if (!module.feature) return true;
  const projectModules = currentProjectModules();
  if (module.feature === "agenda") return Boolean(projectModules.agenda && eventFeature("activities_enabled", true));
  return Boolean(projectModules[module.feature]);
}

function producerModuleAllowed(module) {
  if (!moduleFeatureEnabled(module)) return false;
  if (module.featureFlag && !eventFeatureFlag(module.featureFlag, false)) return false;
  if (module.permissionModule && !canSeeModule(module.permissionModule)) return false;
  if (module.action && !canDo(module.action)) return false;
  if (module.view && !canSeeModule(module.view)) return false;
  return Boolean(module.permissionModule || module.action || module.view);
}

function producerModuleUrl(module) {
  if (module.view) return `#${module.view}`;
  if (module.route) {
    const separator = module.route.includes("?") ? "&" : "?";
    return state.eventId ? `${module.route}${separator}event_id=${encodeURIComponent(state.eventId)}` : module.route;
  }
  return "#home";
}

function openProducerModule(moduleKey) {
  const module = PRODUCER_HOME_MODULES.find((item) => item.key === moduleKey);
  if (!module || !producerModuleAllowed(module)) return;
  if (module.view) {
    setView(module.view);
    history.replaceState(null, "", module.view === "dashboard" ? `${location.pathname}${location.search}` : `#${module.view}`);
    if (module.view === "reports") loadVisualization();
    return;
  }
  location.href = producerModuleUrl(module);
}

function syncProducerHomeEventSelect() {
  const select = $("#producerHomeEventSelect");
  if (!select) return;
  if (select.options.length !== state.events.length) {
    select.innerHTML = eventOptionsHtml();
  }
  select.value = String(state.eventId || "");
}

function formatHomeDate(value) {
  if (!value) return "Fecha sin definir";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" });
}

function renderProducerHome() {
  const grid = $("#producerHomeGrid");
  if (!grid) return;
  const event = currentEvent();
  syncProducerHomeEventSelect();
  $("#homeNav")?.classList.toggle("hidden", !producerHomeAllowed());
  $("#producerHomeSideEvent").textContent = event?.name || "Sin evento activo";
  $("#producerHomeSideDate").textContent = event ? `${formatHomeDate(event.starts_at)} - ${formatHomeDate(event.ends_at)}` : "Selecciona un evento";
  $("#producerHomeRoleBadge").textContent = effectiveRole();
  $("#producerHomeEnv").textContent = state.appConfig?.env || "Staging";
  $("#producerHomeUpdated").textContent = new Date().toLocaleString("es-AR");
  $$(".producer-home-side-link[data-view-target]").forEach((button) => {
    const target = button.dataset.viewTarget;
    const allowed = target === "home" ? producerHomeAllowed() : canSeeModule(target);
    button.classList.toggle("hidden", !allowed);
  });
  updateProducerHomeReturn($(".view.active")?.id || "");
  if (!producerHomeAllowed()) {
    grid.innerHTML = `
      <section class="panel owner-empty">
        <h2>Home no disponible</h2>
        <p>Selecciona un evento activo con permiso de panel para ver los modulos operativos.</p>
      </section>
    `;
    return;
  }
  const modules = PRODUCER_HOME_MODULES.filter(producerModuleAllowed);
  if (!modules.length) {
    grid.innerHTML = `
      <section class="panel owner-empty">
        <h2>Sin modulos habilitados</h2>
        <p>Este usuario no tiene modulos operativos disponibles para el evento activo.</p>
      </section>
    `;
    return;
  }
  grid.innerHTML = modules.map((module) => `
    <button type="button" class="producer-module-card" data-module="${module.key}" aria-label="Abrir ${escapeHtml(module.title)}">
      <span class="producer-module-icon ${module.tone}">${escapeHtml(module.icon)}</span>
      <span class="producer-module-copy">
        <strong>${escapeHtml(module.title)}</strong>
        <small>${escapeHtml(module.description)}</small>
        <em>${escapeHtml(module.metric ? module.metric() : "Modulo habilitado")}</em>
      </span>
      <span class="producer-module-arrow">-></span>
    </button>
  `).join("");
  grid.querySelectorAll("[data-module]").forEach((button) => {
    button.addEventListener("click", () => openProducerModule(button.dataset.module));
  });
}

async function loadPermissions() {
  if (!state.authUser) return;
  const suffix = state.eventId ? `?event_id=${state.eventId}` : "";
  state.permissions = await api(`/api/permissions${suffix}`);
  state.permissionDraft = JSON.parse(JSON.stringify(state.permissions.matrix || {}));
  state.permissionChanges = {};
  renderPermissionsMatrix();
  renderCurrentPermissionsSummary();
  renderProducerHome();
}

function permissionDraftFor(role) {
  return state.permissionDraft?.[role] || { modules: [], actions: [] };
}

function setPermissionsDirty() {
  const count = Object.keys(state.permissionChanges || {}).length;
  $("#permissionsDirtyNotice")?.classList.toggle("hidden", count === 0);
  const saveButton = $("#savePermissionsBtn");
  if (saveButton) saveButton.disabled = count === 0;
}

function renderPermissionsMatrix() {
  const target = $("#permissionsMatrix");
  if (!target || !state.permissions?.matrix) return;
  const modules = Object.keys(MODULE_LABELS);
  const communicationActions = Object.keys(ACTION_LABELS).filter((action) => action.startsWith("communications."));
  const backupActions = Object.keys(ACTION_LABELS).filter((action) => action.startsWith("backups."));
  const integrationActions = Object.keys(ACTION_LABELS).filter((action) => action.startsWith("organizations.") || action.startsWith("integrations.") || action.startsWith("event_integrations."));
  const rows = Object.entries(state.permissions.matrix);
  const locked = state.permissions.locked || {};
  const editable = state.authUser?.role === "Super Admin";
  const renderCell = ({ role, code, allowed, lockedCell = false, kind }) => `
    <label class="permission-check-cell ${allowed ? "yes" : "no"} ${lockedCell ? "locked" : ""}" title="${lockedCell ? "Este permiso esta definido por el sistema." : "Cambiar permiso"}">
      <input
        type="checkbox"
        data-role="${escapeHtml(role)}"
        data-${kind}="${escapeHtml(code)}"
        data-kind="${kind}"
        ${allowed ? "checked" : ""}
        ${!editable || lockedCell ? "disabled" : ""}
        aria-label="${escapeHtml(role)} - ${escapeHtml(kind === "module" ? (MODULE_LABELS[code] || code) : (ACTION_LABELS[code] || code))}"
      >
      <span aria-hidden="true"></span>
    </label>
  `;
  target.innerHTML = `
    <h3 class="permissions-subtitle">Pestanas visibles</h3>
    <div class="permissions-table">
      <div class="permissions-head">
        <strong>Rol</strong>
        ${modules.map((module) => `<span>${MODULE_LABELS[module]}</span>`).join("")}
      </div>
      ${rows.map(([role, config]) => {
        const allowed = new Set(permissionDraftFor(role).modules || config.modules || []);
        return `
          <div class="permissions-row ${role === effectiveRole() ? "current" : ""}">
            <strong>${escapeHtml(role)}</strong>
            ${modules.map((module) => {
              const isAllowed = allowed.has(module);
              const isLocked = (locked[role] || []).includes(module);
              return renderCell({ role, code: module, allowed: isAllowed, lockedCell: isLocked, kind: "module" });
            }).join("")}
          </div>
        `;
      }).join("")}
    </div>
    <h3 class="permissions-subtitle">Permisos finos de Comunicaciones</h3>
    <div class="permissions-table permissions-actions-table">
      <div class="permissions-head permissions-actions-head">
        <strong>Rol</strong>
        ${communicationActions.map((action) => `<span>${ACTION_LABELS[action]}</span>`).join("")}
      </div>
      ${rows.map(([role, config]) => {
        const allowed = new Set(permissionDraftFor(role).actions || config.actions || []);
        return `
          <div class="permissions-row permissions-actions-row ${role === effectiveRole() ? "current" : ""}">
            <strong>${escapeHtml(role)}</strong>
            ${communicationActions.map((action) => renderCell({ role, code: action, allowed: allowed.has(action), kind: "action" })).join("")}
          </div>
        `;
      }).join("")}
    </div>
    <h3 class="permissions-subtitle">Permisos finos de Backups y Persistencia</h3>
    <div class="permissions-table permissions-actions-table">
      <div class="permissions-head permissions-actions-head">
        <strong>Rol</strong>
        ${backupActions.map((action) => `<span>${ACTION_LABELS[action]}</span>`).join("")}
      </div>
      ${rows.map(([role, config]) => {
        const allowed = new Set(permissionDraftFor(role).actions || config.actions || []);
        return `
          <div class="permissions-row permissions-actions-row ${role === effectiveRole() ? "current" : ""}">
            <strong>${escapeHtml(role)}</strong>
            ${backupActions.map((action) => renderCell({ role, code: action, allowed: allowed.has(action), kind: "action" })).join("")}
          </div>
        `;
      }).join("")}
    </div>
    <h3 class="permissions-subtitle">Permisos finos de Organizaciones e Integraciones</h3>
    <div class="permissions-table permissions-actions-table">
      <div class="permissions-head permissions-actions-head">
        <strong>Rol</strong>
        ${integrationActions.map((action) => `<span>${ACTION_LABELS[action]}</span>`).join("")}
      </div>
      ${rows.map(([role, config]) => {
        const allowed = new Set(config.actions || []);
        return `
          <div class="permissions-row permissions-actions-row ${role === effectiveRole() ? "current" : ""}">
            <strong>${escapeHtml(role)}</strong>
            ${integrationActions.map((action) => renderCell({ role, code: action, allowed: allowed.has(action), kind: "action" })).join("")}
          </div>
        `;
      }).join("")}
    </div>
  `;
  target.querySelectorAll(".permission-check-cell input:not(:disabled)").forEach((input) => {
    input.addEventListener("change", queuePermissionChange);
  });
  setPermissionsDirty();
}

function queuePermissionChange(event) {
  const input = event.currentTarget;
  const role = input.dataset.role;
  const module = input.dataset.module;
  const action = input.dataset.action;
  const kind = input.dataset.kind || (action ? "action" : "module");
  const code = kind === "action" ? action : module;
  const allowed = input.checked;
  const config = permissionDraftFor(role);
  const key = kind === "action" ? "actions" : "modules";
  const values = new Set(config[key] || []);
  if (allowed) values.add(code);
  else values.delete(code);
  state.permissionDraft[role] = { ...config, [key]: Array.from(values) };
  state.permissionChanges[`${role}:${kind}:${code}`] = { role, module, action, kind, allowed };
  input.closest(".permission-check-cell")?.classList.toggle("yes", allowed);
  input.closest(".permission-check-cell")?.classList.toggle("no", !allowed);
  setPermissionsDirty();
}

async function savePermissionChanges() {
  const changes = Object.values(state.permissionChanges || {});
  const notice = $("#permissionsNotice");
  if (!changes.length) return;
  const button = $("#savePermissionsBtn");
  if (button) button.disabled = true;
  try {
    let result = null;
    for (const change of changes) {
      result = await api("/api/permissions", {
        method: "POST",
        body: JSON.stringify({ actor: state.currentUser, ...change }),
      });
    }
    if (result?.matrix) {
      state.permissions.matrix = result.matrix;
      state.permissions.locked = result.locked || state.permissions.locked || {};
      state.permissionDraft = JSON.parse(JSON.stringify(result.matrix || {}));
    }
    state.permissionChanges = {};
    if (notice) notice.innerHTML = `<div class="panel success">Cambios guardados.</div>`;
    renderPermissionsMatrix();
    renderCurrentPermissionsSummary();
    renderFeatureVisibility();
  } catch (err) {
    if (notice) notice.innerHTML = `<div class="panel danger">${escapeHtml(err.message || "No se pudieron guardar los permisos")}</div>`;
    setPermissionsDirty();
  }
}

function renderCurrentPermissionsSummary() {
  const target = $("#currentPermissionsSummary");
  if (!target || !state.permissions) return;
  const config = permissionsFor();
  target.innerHTML = `
    <div class="permission-role-card">
      <span class="eyebrow">Rol efectivo</span>
      <h3>${escapeHtml(effectiveRole())}</h3>
      <p>Usuario: ${escapeHtml(state.authUser?.name || "-")} ${state.permissions.role !== state.permissions.effective_role ? `- rol base: ${escapeHtml(state.permissions.role)}` : ""}</p>
    </div>
    <div class="permission-chip-list">
      ${(config.modules || []).map((module) => `<span>${MODULE_LABELS[module] || module}</span>`).join("")}
    </div>
    <div class="permission-action-list">
      ${(config.actions || []).map((action) => `<span>${ACTION_LABELS[action] || action}</span>`).join("")}
    </div>
  `;
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
  if (!state.eventId || !canSeeModule("reports")) return;
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

function eventFeatureFlag(name, fallback = false) {
  const event = currentEvent();
  if (!event || !event.feature_flags || event.feature_flags[name] === undefined) return fallback;
  return Boolean(event.feature_flags[name]);
}

function renderFeatureVisibility() {
  updateProducerChrome();
  const modules = currentProjectModules();
  const activitiesOn = eventFeature("activities_enabled", true);
  const capacityOn = eventFeature("capacity_control_enabled", true);
  const waitlistOn = eventFeature("waitlist_enabled", false);
  $$("nav button[data-view]").forEach((button) => {
    const view = button.dataset.view;
    button.classList.toggle("hidden", view === "home" ? !producerHomeAllowed() : !canSeeModule(view));
  });
  document.querySelector('[data-view="register"]')?.classList.toggle("hidden", !modules.registration || !canSeeModule("register"));
  document.querySelector('[data-view="reception"]')?.classList.toggle("hidden", !modules.reception || !canSeeModule("reception"));
  document.querySelector('[data-view="agenda"]')?.classList.toggle("hidden", !activitiesOn || !modules.agenda || !canSeeModule("agenda"));
  document.querySelector('[data-view="access"]')?.classList.toggle("hidden", !modules.access || !canSeeModule("access"));
  $("#agenda")?.classList.toggle("hidden", !activitiesOn || !modules.agenda);
  $("#displayConfigForm")?.closest(".panel")?.classList.toggle("hidden", !activitiesOn);
  $("#publicDisplayLink")?.classList.toggle("hidden", !activitiesOn);
  $$(".capacity-feature").forEach((node) => node.classList.toggle("hidden", !capacityOn));
  $$(".waitlist-feature").forEach((node) => node.classList.toggle("hidden", !waitlistOn));
  $$(".action-backup").forEach((node) => node.classList.toggle("hidden", !canDo("backups.create_event") || !canDo("backups.download")));
  $("#ticketingModeNotice")?.classList.toggle("hidden", !modules.ticketing);
  $("#dashboard .layout")?.classList.toggle("ticketing-layout", modules.ticketing);
  const activeView = $(".view.active")?.id;
  if (
    (activeView === "home" && !producerHomeAllowed())
    || (activeView !== "home" && !canSeeModule(activeView))
    || (activeView === "register" && !modules.registration)
    || (activeView === "reception" && !modules.reception)
    || (activeView === "agenda" && !modules.agenda)
    || (activeView === "access" && !modules.access)
  ) {
    setView(producerHomeAllowed() ? "home" : canSeeModule("dashboard") ? "dashboard" : permissionsFor().modules[0] || "dashboard");
  }
  renderProducerHome();
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
  renderProducerHome();
}

function eventStatusLabel(status) {
  if (status === "published") return "Publicado";
  if (status === "draft") return "Borrador";
  if (status === "closed") return "Finalizado";
  return status || "Sin estado";
}

function renderOwnerDashboard() {
  const panel = $("#ownerDashboard");
  if (!panel) return;
  if (!state.events.length) {
    panel.innerHTML = `
      <section class="panel owner-empty">
        <h2>Todavia no hay eventos</h2>
        <p>Crea el primer evento para comenzar a operar BITORA.</p>
        <button type="button" data-view-target="configure">Crear evento</button>
      </section>
    `;
  } else {
    panel.innerHTML = state.events.map((event) => {
      const total = Number(event.accreditation_count || 0);
      const checked = Number(event.checked_in_count || 0);
      const pending = Math.max(total - checked, 0);
      return `
        <article class="panel owner-event-card ${Number(event.id) === Number(state.eventId) ? "active" : ""}">
          <div class="owner-event-head">
            <div>
              <span class="eyebrow">${eventStatusLabel(event.status)}</span>
              <h2>${escapeHtml(event.name)}</h2>
              <p>${escapeHtml(event.venue || "Sin lugar definido")}</p>
            </div>
            <strong>${event.project_type === "ticketing" ? "Ticketing" : "Conference"}</strong>
          </div>
          <div class="owner-event-metrics">
            <div><strong>${total}</strong><span>Inscriptos</span></div>
            <div><strong>${checked}</strong><span>Acreditados</span></div>
            <div><strong>${pending}</strong><span>Pendientes</span></div>
          </div>
          <div class="owner-event-actions">
            <button type="button" class="open-owner-event" data-id="${event.id}">Entrar al evento</button>
            <a class="button ghost" href="/e.html?event_id=${event.id}" target="_blank">Landing</a>
            <a class="button ghost" href="/display.html?event_id=${event.id}" target="_blank">Pantalla publica</a>
          </div>
        </article>
      `;
    }).join("");
  }
  panel.querySelectorAll("[data-view-target]").forEach((button) => button.addEventListener("click", () => {
    setView(button.dataset.viewTarget);
    history.replaceState(null, "", `#${button.dataset.viewTarget}`);
  }));
  panel.querySelectorAll(".open-owner-event").forEach((button) => button.addEventListener("click", async () => {
    await selectActiveEvent(button.dataset.id);
    setView("dashboard");
    history.replaceState(null, "", `/?event_id=${state.eventId}`);
  }));
}

async function reloadCurrentEventData() {
  if (!state.eventId) return;
  const loaders = [
    ["types", loadTypes],
    ["accreditations", loadAccreditations],
    ["agenda", loadAgenda],
    ["alerts", loadAlerts],
    ["system_status", loadSystemStatus],
    ["network_info", loadNetworkInfo],
    ["summary", loadSummary],
    ["marketing", loadMarketing],
    ["readiness", loadReadiness],
    ["audit", loadAudit],
    ["communications", loadCommunications],
    ["demo_real", loadDemoReal],
    ["logs", loadLogs],
    ["event_users", loadEventUsers],
  ];
  const results = await Promise.allSettled(loaders.map(([, loader]) => loader()));
  results.forEach((result, index) => {
    if (result.status === "rejected") {
      console.warn(`No se pudo cargar ${loaders[index][0]}`, result.reason);
    }
  });
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

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file) return reject(new Error("Selecciona un archivo"));
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("No se pudo leer el archivo"));
    reader.readAsDataURL(file);
  });
}

async function inspectEventBackup(event) {
  event.preventDefault();
  const file = $("#eventRestoreFile")?.files?.[0];
  const target = $("#eventRestorePreview");
  if (!target) return;
  try {
    if (!canDo("backups.restore_event")) throw new Error("Tu rol no tiene permiso para restaurar eventos.");
    if (!file) throw new Error("Selecciona un backup ZIP de evento.");
    if (!file.name.toLowerCase().endsWith(".zip")) throw new Error("Selecciona un archivo ZIP.");
    $("#eventRestoreFileName").textContent = file.name;
    target.innerHTML = `<div class="panel">Verificando manifiesto y checksum...</div>`;
    const content = await readFileAsDataUrl(file);
    const result = await api("/api/backups/event/inspect", {
      method: "POST",
      body: JSON.stringify({ filename: file.name, content_base64: content }),
    });
    state.eventRestore = result;
    renderEventRestorePreview();
  } catch (err) {
    target.innerHTML = `<div class="panel danger">${escapeHtml(err.message)}</div>`;
  }
}

function renderEventRestorePreview() {
  const target = $("#eventRestorePreview");
  const data = state.eventRestore;
  if (!target || !data) return;
  const counts = data.counts || {};
  const event = data.event || {};
  const manifest = data.manifest || {};
  const warnings = data.warnings || [];
  const conflicts = data.conflicts || [];
  target.innerHTML = `
    <div class="restore-summary">
      <div>
        <span>Evento origen</span>
        <strong>${escapeHtml(event.name || "Evento")}</strong>
        <small>ID origen ${escapeHtml(event.source_event_id || "")} - ${escapeHtml(manifest.created_at || "")}</small>
      </div>
      <div><span>Participantes</span><strong>${Number(counts.participants || 0)}</strong></div>
      <div><span>Acreditaciones</span><strong>${Number(counts.accreditations || 0)}</strong></div>
      <div><span>Actividades</span><strong>${Number(counts.activities || 0)}</strong></div>
      <div><span>Reservas</span><strong>${Number(counts.reservations || 0)}</strong></div>
      <div><span>Accesos</span><strong>${Number(counts.accesses || 0)}</strong></div>
      <div><span>Comunicaciones</span><strong>${Number(counts.communications || 0)}</strong></div>
      <div><span>Checksum</span><strong>${manifest.sha256 ? "OK" : "Sin dato"}</strong></div>
    </div>
    ${warnings.length ? `<div class="panel warn">${warnings.map(escapeHtml).join("<br>")}</div>` : ""}
    ${conflicts.length ? `<div class="panel warn">${conflicts.length} advertencias/conflictos detectados. Se reutilizan personas existentes por email cuando corresponde.</div>` : ""}
    <form id="eventRestoreRunForm" class="stack restore-run-form">
      <input name="new_event_name" value="${escapeHtml(`${event.name || "Evento"} - restaurado`)}" placeholder="Nombre del evento restaurado">
      <button type="submit">Restaurar como nuevo evento</button>
    </form>
    <details class="danger-zone">
      <summary>Sobrescribir evento existente (avanzado)</summary>
      <form id="eventRestoreOverwriteForm" class="stack">
        <select name="target_event_id">
          ${state.events.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("")}
        </select>
        <input name="new_event_name" value="${escapeHtml(event.name || "Evento restaurado")}" placeholder="Nombre a aplicar">
        <input name="confirm_text" placeholder="Escribir RESTAURAR EVENTO">
        <button class="danger-button" type="submit" ${canDo("backups.restore_event_overwrite") ? "" : "disabled"}>Sobrescribir evento</button>
        ${canDo("backups.restore_event_overwrite") ? "" : "<small>Requiere permiso especial de sobrescritura.</small>"}
      </form>
    </details>
    <div id="eventRestoreResult"></div>
  `;
  $("#eventRestoreRunForm")?.addEventListener("submit", restoreEventBackupAsNew);
  $("#eventRestoreOverwriteForm")?.addEventListener("submit", restoreEventBackupOverwrite);
}

async function restoreEventBackupAsNew(event) {
  event.preventDefault();
  await restoreEventBackup({
    mode: "new_event",
    new_event_name: event.currentTarget.elements.new_event_name.value,
  });
}

async function restoreEventBackupOverwrite(event) {
  event.preventDefault();
  const form = event.currentTarget;
  await restoreEventBackup({
    mode: "overwrite",
    target_event_id: Number(form.elements.target_event_id.value || 0),
    new_event_name: form.elements.new_event_name.value,
    confirm_text: form.elements.confirm_text.value,
  });
}

async function restoreEventBackup(payload) {
  const box = $("#eventRestoreResult");
  try {
    if (!state.eventRestore?.restore_id) throw new Error("Primero inspecciona el backup.");
    box.innerHTML = `<div class="panel">Restaurando dentro de una transaccion...</div>`;
    const result = await api("/api/backups/event/restore", {
      method: "POST",
      body: JSON.stringify({ restore_id: state.eventRestore.restore_id, ...payload }),
    });
    box.innerHTML = `
      <div class="panel success">
        Evento restaurado: <strong>${escapeHtml(result.name || "")}</strong>.
        Nuevo ID: ${Number(result.event_id || 0)}.
        Tokens regenerados: ${Number(result.token_regenerated || 0)}.
      </div>
    `;
    state.eventRestore = null;
    await loadEvents();
    if (result.event_id) {
      await selectActiveEvent(result.event_id);
      setView("dashboard");
    }
  } catch (err) {
    box.innerHTML = `<div class="panel danger">${escapeHtml(err.message)}</div>`;
  }
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
  if (!state.selectedUserId || !state.users.some((row) => Number(row.id) === Number(state.selectedUserId))) {
    state.selectedUserId = state.users.find((row) => row.name === state.currentUser)?.id || state.users[0]?.id || null;
  }
  renderUsersList();
  renderSelectedUserDetail();
  const resetSelect = $("#passwordResetUser");
  if (resetSelect) {
    resetSelect.innerHTML = state.users.map((row) => `<option value="${row.id}">${escapeHtml(row.name)} - ${escapeHtml(row.role)}</option>`).join("");
    if (state.selectedUserId) resetSelect.value = String(state.selectedUserId);
  }
}

function userInitials(row) {
  const source = String(row.full_name || row.name || "?").trim();
  const parts = source.split(/\s+/).filter(Boolean);
  return (parts.length > 1 ? `${parts[0][0]}${parts[1][0]}` : source.slice(0, 2)).toUpperCase();
}

function selectedUser() {
  return state.users.find((row) => Number(row.id) === Number(state.selectedUserId)) || null;
}

function renderUsersList() {
  const list = $("#usersList");
  if (!list) return;
  const term = ($("#userSearchInput")?.value || "").trim().toLowerCase();
  const rows = state.users.filter((row) => {
    const text = `${row.name || ""} ${row.full_name || ""} ${row.email || ""} ${row.role || ""}`.toLowerCase();
    return !term || text.includes(term);
  });
  list.innerHTML = rows.map((row) => `
    <article class="user-clean-row ${Number(row.id) === Number(state.selectedUserId) ? "selected" : ""}" data-user-id="${row.id}">
      <button type="button" class="user-select-button" data-user-id="${row.id}">
        <span class="user-avatar">${escapeHtml(userInitials(row))}</span>
        <span class="user-main">
          <strong>${escapeHtml(row.name)}</strong>
          <small>${escapeHtml(row.role)}${Number(row.active) ? "" : " · inactivo"}${Number(row.must_change_password) ? " · cambia clave" : ""}</small>
        </span>
      </button>
      ${state.authUser?.role === "Super Admin" ? `
        <button type="button" class="ghost user-edit-action" data-user-id="${row.id}">Editar</button>
        <button type="button" class="danger-outline user-delete-action" data-user-id="${row.id}">Eliminar</button>
      ` : ""}
    </article>
  `).join("") || `<p class="empty">No hay usuarios para esa busqueda.</p>`;
  list.querySelectorAll(".user-select-button").forEach((button) => button.addEventListener("click", () => selectUser(button.dataset.userId)));
  list.querySelectorAll(".user-edit-action").forEach((button) => button.addEventListener("click", () => editUser(button.dataset.userId)));
  list.querySelectorAll(".user-delete-action").forEach((button) => button.addEventListener("click", () => deleteUser(button.dataset.userId)));
}

function renderSelectedUserDetail() {
  const target = $("#selectedUserDetail");
  if (!target) return;
  const row = selectedUser();
  if (!row) {
    target.innerHTML = `<p class="empty">Selecciona un usuario para ver detalle.</p>`;
    return;
  }
  target.innerHTML = `
    <div class="selected-user-card">
      <span class="user-avatar large">${escapeHtml(userInitials(row))}</span>
      <div>
        <span class="eyebrow">Usuario seleccionado</span>
        <h2>${escapeHtml(row.name)}</h2>
        <p>${escapeHtml(row.full_name || "Sin nombre completo")} · ${escapeHtml(row.email || "Sin email")}</p>
      </div>
      <span class="role-pill">${escapeHtml(row.role)}</span>
    </div>
    <div class="selected-user-actions">
      <button type="button" class="ghost" id="selectedUserEditBtn">Editar usuario</button>
      ${state.authUser?.role === "Super Admin" ? `<button type="button" class="ghost user-status-action" data-user-id="${row.id}" data-active="${Number(row.active) ? "0" : "1"}">${Number(row.active) ? "Desactivar" : "Activar"}</button>` : ""}
      ${state.authUser?.role === "Super Admin" ? `<button type="button" class="danger-outline" id="selectedUserDeleteBtn">Eliminar</button>` : ""}
    </div>
  `;
  $("#selectedUserEditBtn")?.addEventListener("click", () => editUser(row.id));
  $("#selectedUserDeleteBtn")?.addEventListener("click", () => deleteUser(row.id));
  target.querySelector(".user-status-action")?.addEventListener("click", toggleUserStatus);
}

function selectUser(userId) {
  state.selectedUserId = Number(userId);
  const resetSelect = $("#passwordResetUser");
  if (resetSelect) resetSelect.value = String(userId);
  renderUsersList();
  renderSelectedUserDetail();
}

function editUser(userId) {
  selectUser(userId);
  const row = selectedUser();
  const form = $("#userForm");
  if (!row || !form) return;
  form.closest("details")?.setAttribute("open", "open");
  form.elements.name.value = row.name || "";
  form.elements.full_name.value = row.full_name || "";
  form.elements.email.value = row.email || "";
  form.elements.role.value = row.role || "Visualizador";
  form.elements.pin.value = "";
  form.elements.must_change_password.checked = Boolean(Number(row.must_change_password || 0));
  form.elements.active.checked = Boolean(Number(row.active || 0));
}

async function deleteUser(userId) {
  const row = state.users.find((item) => Number(item.id) === Number(userId));
  if (!row) return;
  const ok = confirm(`Eliminar usuario\n\nEstas seguro de que queres eliminar al usuario "${row.name}"?\n\nEsta accion no se puede deshacer.`);
  if (!ok) return;
  try {
    await api("/api/users/delete", {
      method: "POST",
      body: JSON.stringify({ actor: state.currentUser, user_id: userId }),
    });
    $("#userNotice").innerHTML = `<div class="panel success">Usuario eliminado correctamente.</div>`;
    if (Number(state.selectedUserId) === Number(userId)) state.selectedUserId = null;
    await Promise.all([loadUsers(), loadEventUsers(), loadAudit()]);
  } catch (err) {
    $("#userNotice").innerHTML = `<div class="panel danger">${escapeHtml(err.message || "No se pudo eliminar el usuario")}</div>`;
  }
}
async function loadEventUsers() {
  const panel = $("#eventUsersList");
  if (!panel || !state.eventId) return;
  if (!canSeeModule("users")) {
    panel.innerHTML = `<p class="empty">Equipo visible solo para administracion del evento.</p>`;
    return;
  }
  try {
    const result = await api(`/api/event-users?event_id=${state.eventId}`);
    state.eventUsers = result.items || [];
    const roles = result.roles || Object.keys(state.permissions?.matrix || {});
    panel.innerHTML = state.eventUsers.map((row) => `
      <form class="event-user-row ${Number(row.assigned) ? "assigned" : ""}" data-user-id="${row.user_id}">
        <label class="toggle">
          <input name="assigned" type="checkbox" ${Number(row.assigned) ? "checked" : ""}>
          <span>${escapeHtml(row.name)}</span>
        </label>
        <select name="role">
          ${roles.map((role) => `<option value="${role}" ${role === row.event_role ? "selected" : ""}>${role}</option>`).join("")}
        </select>
        <small>${escapeHtml(row.platform_role)}</small>
        <button>Guardar</button>
      </form>
    `).join("") || `<p class="empty">Todavia no hay usuarios activos.</p>`;
    panel.querySelectorAll(".event-user-row").forEach((form) => form.addEventListener("submit", saveEventUser));
  } catch (err) {
    panel.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function saveEventUser(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = state.eventId;
  data.user_id = form.dataset.userId;
  data.assigned = form.elements.assigned.checked;
  data.actor = state.currentUser;
  await api("/api/event-users", { method: "POST", body: JSON.stringify(data) });
  await Promise.all([loadEventUsers(), loadAudit()]);
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
  if (!canDo("communications.view")) {
    $("#communicationNotice").innerHTML = `<div class="panel danger">No tenes permiso para acceder al Centro de Comunicaciones de este evento.</div>`;
    return;
  }
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
  $("#communicationV5Metrics").innerHTML = canDo("communications.view_metrics") ? `
    <div><strong>${Number(queueMetrics.emails_sent || 0)}</strong><span>Emails enviados</span></div>
    <div><strong>${Number(queueMetrics.emails_delivered || 0)}</strong><span>Emails entregados</span></div>
    <div><strong>${Number(queueMetrics.emails_bounced || 0)}</strong><span>Rebotes</span></div>
    <div><strong>${Number(queueMetrics.emails_failed || 0)}</strong><span>Email fallidos</span></div>
    <div><strong>${Number(queueMetrics.whatsapp_sent || 0)}</strong><span>WhatsApp enviados</span></div>
    <div><strong>${Number(queueMetrics.whatsapp_delivered || 0)}</strong><span>WhatsApp entregados</span></div>
    <div><strong>${Number(queueMetrics.whatsapp_read || 0)}</strong><span>WhatsApp leidos</span></div>
    <div><strong>${Number(queueMetrics.pending || 0)}</strong><span>Pendientes</span></div>
    <div><strong>${Number(queueMetrics.errors || 0)}</strong><span>Errores</span></div>
  ` : `<p class="empty">Requiere permiso de metricas.</p>`;
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
    emailTestForm.classList.toggle("hidden", !canDo("communications.manage_providers"));
  }
  await loadGoogleOAuthPanel();
  $("#whatsappTestForm")?.classList.toggle("hidden", !canDo("communications.manage_providers"));
  $("#communicationForm")?.classList.toggle("hidden", !canDo("communications.create") && !canDo("communications.send"));
  $("#communicationForm")?.querySelector('[name="audience"]')?.toggleAttribute("disabled", !canDo("communications.select_audience"));
  $("#communicationForm")?.querySelector('[name="confirm"]')?.toggleAttribute("disabled", !canDo("communications.send"));
  const communicationSubmit = $("#communicationForm")?.querySelector('button');
  if (communicationSubmit) {
    communicationSubmit.textContent = canDo("communications.send") ? "Crear cola de envio" : "Guardar borrador";
    communicationSubmit.title = canDo("communications.send") ? "" : "Requiere autorizacion de envio para procesar la cola";
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
  $("#communicationTemplates").closest(".panel")?.classList.toggle("hidden", !canDo("communications.manage_templates") && !canDo("communications.create") && !canDo("communications.send"));
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
  $("#communicationLogs").closest(".panel")?.classList.toggle("hidden", !canDo("communications.view_history"));
  $("#communicationLogs").innerHTML = canDo("communications.view_history") ? state.communications.logs.map((row) => `
    <article class="audit-row">
      <div>
        <strong>${row.asunto || row.tipo}</strong>
        <span>${row.first_name} ${row.last_name} - ${row.canal} - ${row.estado} - ${new Date(row.fecha).toLocaleString()}</span>
      </div>
      <code>${row.tipo}</code>
    </article>
  `).join("") || `<p class="empty">Todavia no hay comunicaciones registradas.</p>` : `<p class="empty">Requiere permiso para ver historial.</p>`;
  $$(".template-pick").forEach((button) => button.addEventListener("click", () => {
    const form = $("#communicationForm");
    form.elements.type.value = button.dataset.type;
    form.elements.subject.value = button.dataset.subject;
    form.elements.content.value = button.dataset.content;
    form.dataset.templateCode = button.dataset.code;
  }));
}

function googleOAuthNotice(message, kind = "") {
  const target = $("#googleOAuthNotice");
  if (!target) return;
  target.textContent = message || "";
  target.className = `result ${kind}`.trim();
}

async function loadGoogleOAuthPanel() {
  const summary = $("#googleOAuthSummary");
  if (!summary || !state.eventId || !canDo("integrations.view")) return;
  try {
    const eventIntegrations = await api(`/api/event-integrations?event_id=${state.eventId}`);
    const assigned = (eventIntegrations.items || []).find((row) => row.provider === "google" && row.channel === "google");
    const available = (eventIntegrations.available || []).find((row) => row.provider === "google" && ["oauth_provider", "google_oauth"].includes(row.integration_type));
    const integration = assigned || available || null;
    state.googleOAuth = {
      organization_id: eventIntegrations.organization_id,
      integration_id: integration ? Number(integration.organization_integration_id || integration.id) : 0,
      assigned: Boolean(assigned),
    };
    let status = { google: { enabled: false, ready: false, scopes: [], errors: [] }, integration: integration || null };
    if (state.googleOAuth.integration_id) {
      status = await api(`/api/integrations/google/status?integration_id=${state.googleOAuth.integration_id}`);
      state.googleOAuth.status = status;
    }
    const google = status.google || {};
    const item = status.integration || integration || {};
    summary.innerHTML = `
      <div><strong>${item.status || "Sin integracion"}</strong><span>Estado</span></div>
      <div><strong>${google.ready ? "Lista" : "No configurada"}</strong><span>Google OAuth</span></div>
      <div><strong>${google.account_email || "Sin cuenta"}</strong><span>Cuenta</span></div>
      <div><strong>${(google.granted_scopes || google.scopes || []).join(", ") || "Sin scopes"}</strong><span>Scopes</span></div>
      <div><strong>${google.expires_at || "Sin vencimiento"}</strong><span>Expira</span></div>
      <div><strong>${google.last_refresh_at || "Sin refresh"}</strong><span>Ultimo refresh</span></div>
    `;
    $("#googleCreateIntegrationBtn")?.toggleAttribute("disabled", !canDo("integrations.create") || Boolean(state.googleOAuth.integration_id));
    $("#googleConnectBtn")?.toggleAttribute("disabled", !canDo("integrations.google_connect") || !state.googleOAuth.integration_id);
    $("#googleTestBtn")?.toggleAttribute("disabled", !canDo("integrations.test") || !state.googleOAuth.integration_id);
    $("#googleRefreshBtn")?.toggleAttribute("disabled", !canDo("integrations.google_refresh") || !state.googleOAuth.integration_id);
    $("#googleDisconnectBtn")?.toggleAttribute("disabled", !canDo("integrations.google_disconnect") || !state.googleOAuth.integration_id);
    if ((google.errors || []).length) {
      googleOAuthNotice(`Google OAuth pendiente: ${google.errors.join("; ")}`, "warning");
    } else {
      googleOAuthNotice("");
    }
  } catch (error) {
    googleOAuthNotice(error.message, "error");
  }
}

async function createGoogleIntegration() {
  if (!state.eventId) return;
  try {
    const eventIntegrations = await api(`/api/event-integrations?event_id=${state.eventId}`);
    const created = await api("/api/organization-integrations", {
      method: "POST",
      body: JSON.stringify({
        actor: state.currentUser,
        organization_id: eventIntegrations.organization_id,
        provider: "google",
        integration_type: "oauth_provider",
        name: "Google OAuth",
        mode: "client_owned",
        status: "disconnected",
        metadata: { requested_scopes: ["openid", "email", "profile"] },
      }),
    });
    await api("/api/event-integrations", {
      method: "POST",
      body: JSON.stringify({
        actor: state.currentUser,
        event_id: state.eventId,
        channel: "google",
        organization_integration_id: created.integration.id,
        enabled: true,
        is_default: true,
      }),
    });
    googleOAuthNotice("Integracion Google creada para este evento.", "success");
    await loadGoogleOAuthPanel();
  } catch (error) {
    googleOAuthNotice(error.message, "error");
  }
}

async function connectGoogleIntegration() {
  if (!state.googleOAuth?.integration_id) return googleOAuthNotice("Primero crea una integracion Google.", "warning");
  try {
    const result = await api("/api/integrations/google/connect", {
      method: "POST",
      body: JSON.stringify({
        actor: state.currentUser,
        integration_id: state.googleOAuth.integration_id,
        redirect_after: `/?event_id=${state.eventId}&view=configure`,
      }),
    });
    location.href = result.authorization_url;
  } catch (error) {
    googleOAuthNotice(error.message, "error");
  }
}

async function googleIntegrationAction(action) {
  if (!state.googleOAuth?.integration_id) return googleOAuthNotice("Primero crea una integracion Google.", "warning");
  const paths = {
    test: "/api/integrations/google/test",
    refresh: "/api/integrations/google/refresh",
    disconnect: "/api/integrations/google/disconnect",
  };
  try {
    const result = await api(paths[action], {
      method: "POST",
      body: JSON.stringify({ actor: state.currentUser, integration_id: state.googleOAuth.integration_id, revoke: action === "disconnect" }),
    });
    googleOAuthNotice(result.status ? `Google: ${result.status}` : "Operacion Google completada.", result.ok === false ? "error" : "success");
    await loadGoogleOAuthPanel();
  } catch (error) {
    googleOAuthNotice(error.message, "error");
  }
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
  renderContextAgendaPanels();
  renderReservationSelectors();
  renderAccessActivitySelector();
  renderReservations();
  renderCapacityBags();
  $$(".activity-row").forEach((row) => row.addEventListener("click", (event) => {
    if (event.target.closest("a,button")) return;
    openActivityDetail(row.dataset.id);
  }));
}

function renderContextAgendaPanels() {
  const targets = ["registerAgendaContext", "receptionAgendaContext"];
  const allowedTypes = new Set(["charla", "workshop", "panel", "capacitacion", "networking"]);
  const rows = [...(state.activities || [])]
    .filter((row) => allowedTypes.has(String(row.activity_type || "").trim().toLowerCase()))
    .sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at));
  const html = rows.slice(0, 10).map((row) => `
    <article class="context-agenda-row">
      <time>${new Date(row.starts_at).toLocaleDateString()} ${new Date(row.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>
      <div>
        <strong>${escapeHtml(row.title)}</strong>
        <span>${escapeHtml(row.space_name || "Sin sala")} - ${escapeHtml(row.activity_type || "Actividad")}</span>
      </div>
      <small>${activityCapacityLabel(row)}</small>
    </article>
  `).join("");
  targets.forEach((id) => {
    const panel = $(`#${id}`);
    if (!panel) return;
    panel.innerHTML = html || `<p class="empty">Este evento todavia no tiene charlas cargadas.</p>`;
  });
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
  const result = await api("/api/events", { method: "POST", body: JSON.stringify(data) });
  form.reset();
  state.eventId = Number(result.id || state.eventId || 0);
  await loadEvents();
  setView("dashboard");
  history.replaceState(null, "", `/?event_id=${state.eventId}`);
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
  const notice = $("#userNotice");
  try {
    const data = formData(form);
    data.actor = state.currentUser;
    data.must_change_password = form.elements.must_change_password.checked;
    data.active = form.elements.active.checked;
    const result = await api("/api/users", { method: "POST", body: JSON.stringify(data) });
    form.reset();
    form.elements.must_change_password.checked = true;
    form.elements.active.checked = true;
    if (notice) notice.innerHTML = `<div class="panel success">Usuario guardado: ${escapeHtml(result.user?.name || data.name)}</div>`;
    const refreshes = await Promise.allSettled([loadUsers(), loadEventUsers(), loadAudit()]);
    refreshes.forEach((refresh) => {
      if (refresh.status === "rejected") console.warn("No se pudo refrescar usuarios despues de guardar", refresh.reason);
    });
  } catch (err) {
    if (notice) notice.innerHTML = `<div class="panel danger">${escapeHtml(err.message || "No se pudo guardar el usuario")}</div>`;
  }
}

async function resetUserPassword(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.actor = state.currentUser;
  data.generate_password = form.elements.generate_password.checked;
  const result = await api("/api/users/password-reset", { method: "POST", body: JSON.stringify(data) });
  $("#passwordResetNotice").innerHTML = result.temporary_password
    ? `<div class="panel warning"><strong>Contraseña temporal:</strong> <code>${escapeHtml(result.temporary_password)}</code><br><small>Copiala ahora. BITORA no volvera a mostrarla.</small></div>`
    : `<div class="panel success">Contraseña restablecida. El usuario debera cambiarla al ingresar.</div>`;
  form.reset();
  await Promise.all([loadUsers(), loadAudit()]);
}

async function toggleUserStatus(event) {
  const button = event.currentTarget;
  await api("/api/users/status", {
    method: "POST",
    body: JSON.stringify({ actor: state.currentUser, user_id: button.dataset.userId, active: button.dataset.active === "1" }),
  });
  await Promise.all([loadUsers(), loadEventUsers(), loadAudit()]);
}

async function changeOwnPassword(event) {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    await api("/api/auth/change-password", { method: "POST", body: JSON.stringify(formData(form)) });
    $("#passwordChangeNotice").innerHTML = `<div class="panel success">Contraseña actualizada.</div>`;
    state.authUser.must_change_password = 0;
    form.reset();
    await loadEvents();
    setView(producerHomeAllowed() ? "home" : "dashboard");
  } catch (err) {
    $("#passwordChangeNotice").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

async function sendDemoCommunication(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!canDo("communications.create") && !canDo("communications.send")) {
    $("#communicationNotice").innerHTML = `<div class="panel danger">No tenes permiso para crear comunicaciones en este evento.</div>`;
    return;
  }
  const data = formData(form);
  data.event_id = state.eventId;
  data.actor = state.currentUser;
  data.template_code = form.dataset.templateCode || form.elements.type.value;
  data.type = form.elements.type.value;
  data.confirm = canDo("communications.send") && form.elements.confirm.checked;
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
    if (button.dataset.view === "home") {
      if (!producerHomeAllowed()) return;
    } else if (!canSeeModule(button.dataset.view)) {
      return;
    }
    setView(button.dataset.view);
    if (button.dataset.view === "diagnostics") loadDiagnostics();
    if (button.dataset.view === "simulator") loadSimulator();
    if (button.dataset.view === "reports") loadVisualization();
    const url = button.dataset.view === "dashboard" ? `${location.pathname}${location.search}` : `#${button.dataset.view}`;
    history.replaceState(null, "", url);
  }));
  $$("[data-view-target]").forEach((button) => button.addEventListener("click", () => {
    const target = button.dataset.viewTarget;
    if (target === "home") {
      if (!producerHomeAllowed()) return;
    } else if (!canSeeModule(target)) {
      return;
    }
    setView(target);
    history.replaceState(null, "", target === "dashboard" ? `${location.pathname}${location.search}` : `#${target}`);
  }));
  $("#eventSelect").addEventListener("change", async (event) => {
    await selectActiveEvent(event.target.value);
  });
  $("#producerHomeEventSelect")?.addEventListener("change", async (event) => {
    await selectActiveEvent(event.target.value);
  });
  $("#producerHomeRefreshBtn")?.addEventListener("click", loadEvents);
  $("#usersEventSelect")?.addEventListener("change", async (event) => {
    await selectActiveEvent(event.target.value);
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
  $("#eventRestoreInspectForm")?.addEventListener("submit", inspectEventBackup);
  $("#eventRestoreFile")?.addEventListener("change", (event) => {
    const file = event.currentTarget.files?.[0];
    $("#eventRestoreFileName").textContent = file ? file.name : "Ningun archivo seleccionado";
  });
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
  $("#userSearchInput")?.addEventListener("input", renderUsersList);
  $("#passwordResetForm")?.addEventListener("submit", resetUserPassword);
  $("#savePermissionsBtn")?.addEventListener("click", savePermissionChanges);
  $("#passwordChangeForm")?.addEventListener("submit", changeOwnPassword);
  $("#communicationForm").addEventListener("submit", sendDemoCommunication);
  $("#emailTestForm")?.addEventListener("submit", sendTestEmail);
  $("#whatsappTestForm")?.addEventListener("submit", sendTestWhatsApp);
  $("#googleCreateIntegrationBtn")?.addEventListener("click", createGoogleIntegration);
  $("#googleConnectBtn")?.addEventListener("click", connectGoogleIntegration);
  $("#googleTestBtn")?.addEventListener("click", () => googleIntegrationAction("test"));
  $("#googleRefreshBtn")?.addEventListener("click", () => googleIntegrationAction("refresh"));
  $("#googleDisconnectBtn")?.addEventListener("click", () => googleIntegrationAction("disconnect"));
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
  if (state.authUser?.must_change_password) {
    initialView = "passwordChange";
  }
  if (initialView === "visualization") initialView = "reports";
  if (!initialView && producerDefaultView()) {
    initialView = producerDefaultView();
  } else if (!initialView && state.authUser?.role === "Super Admin" && !new URLSearchParams(location.search).get("event_id")) {
    initialView = "owner";
  }
  if (initialView === "home" && !producerHomeAllowed()) {
    initialView = canSeeModule("dashboard") ? "dashboard" : permissionsFor().modules[0] || "dashboard";
  } else if (initialView && initialView !== "home" && !canSeeModule(initialView)) {
    initialView = permissionsFor().modules[0] || "dashboard";
  }
  if (initialView && document.getElementById(initialView)?.classList.contains("view")) {
    setView(initialView);
    if (initialView === "diagnostics") await loadDiagnostics();
    if (initialView === "simulator") await loadSimulator();
    if (initialView === "reports") await loadVisualization();
  }
});
