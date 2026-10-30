const $ = (selector) => document.querySelector(selector);
const params = new URLSearchParams(location.search);
const eventId = Number(params.get("event_id") || 0);
const source = (params.get("source") || params.get("utm_source") || "landing").toLowerCase();
const sourceDetail = params.get("source_detail") || params.get("utm_campaign") || params.get("qr") || "";
const sessionId = localStorage.getItem("captation_session") || crypto.randomUUID();
localStorage.setItem("captation_session", sessionId);
const waitingVisitorId = localStorage.getItem(`waiting_visitor_${eventId}`) || crypto.randomUUID();
localStorage.setItem(`waiting_visitor_${eventId}`, waitingVisitorId);
let currentEvent = null;
let formStarted = false;
let waitingTimer = null;
let registrationSubmitting = false;
const registrationAttemptStorageKey = `bitora_registration_attempt_${eventId}`;
const REGISTRATION_TIMEOUT_MS = 15000;
const REGISTRATION_MAX_ATTEMPTS = 3;

class ApiError extends Error {
  constructor(message, { status = 0, code = "REQUEST_FAILED", retryable = false } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryable = retryable;
  }
}

const eventThemes = [
  { primary: "#4c2ea3", secondary: "#1b0f4e", accent: "#20c7b5", soft: "#f4f1ff" },
  { primary: "#0b6f7a", secondary: "#07333d", accent: "#d4a23a", soft: "#eefafa" },
  { primary: "#9d3f34", secondary: "#431816", accent: "#efb75c", soft: "#fff3ef" },
  { primary: "#1f5f3d", secondary: "#0d2f20", accent: "#bddf7a", soft: "#f1f8ec" },
  { primary: "#244f93", secondary: "#102647", accent: "#6dd6ff", soft: "#eef5ff" },
];

function hashText(text) {
  return [...String(text || "bitora")].reduce((acc, char) => acc + char.charCodeAt(0), 0);
}

function applyEventTheme(event) {
  const theme = eventThemes[hashText(event.name) % eventThemes.length];
  const root = document.documentElement;
  root.style.setProperty("--event-primary", event.theme_color || theme.primary);
  root.style.setProperty("--event-secondary", event.theme_dark || theme.secondary);
  root.style.setProperty("--event-accent", event.theme_accent || theme.accent);
  root.style.setProperty("--event-soft", event.theme_soft || theme.soft);
  if (event.landing_image_data) {
    root.style.setProperty("--landing-image", `url("${event.landing_image_data}")`);
    document.body.classList.add("has-landing-image");
  } else {
    root.style.setProperty("--landing-image", "none");
    document.body.classList.remove("has-landing-image");
  }
}

function deviceType() {
  const width = window.innerWidth || screen.width;
  const ua = navigator.userAgent || "";
  if (/ipad|tablet/i.test(ua) || (width >= 700 && width <= 1100 && /mobile|android/i.test(ua))) return "tablet";
  if (width < 760 || /iphone|android|mobile/i.test(ua)) return "mobile";
  return "desktop";
}

async function api(path, options = {}) {
  const { timeoutMs = 0, headers: optionHeaders = {}, ...fetchOptions } = options;
  const controller = timeoutMs ? new AbortController() : null;
  const timeout = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const response = await fetch(path, {
      ...fetchOptions,
      headers: { "Content-Type": "application/json", ...optionHeaders },
      ...(controller ? { signal: controller.signal } : {}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const code = data.code || "REQUEST_FAILED";
      throw new ApiError(data.error || `Solicitud rechazada (${response.status})`, {
        status: response.status,
        code,
        retryable: [502, 503, 504].includes(response.status) || code === "REGISTRATION_IDEMPOTENCY_PENDING",
      });
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const timedOut = error?.name === "AbortError";
    throw new ApiError(
      timedOut ? "La confirmacion esta demorando mas de lo esperado." : "No se pudo confirmar la respuesta del servidor.",
      { code: timedOut ? "REQUEST_TIMEOUT" : "NETWORK_ERROR", retryable: true },
    );
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

async function payloadHash(payload) {
  const bytes = new TextEncoder().encode(stableJson(payload));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function newRequestId() {
  return crypto.randomUUID();
}

function readRegistrationAttempt() {
  try {
    const attempt = JSON.parse(sessionStorage.getItem(registrationAttemptStorageKey) || "null");
    if (!attempt || attempt.eventId !== eventId || !attempt.key || !attempt.correlationId || !attempt.payloadHash) return null;
    return attempt;
  } catch (_) {
    return null;
  }
}

function writeRegistrationAttempt(attempt) {
  try {
    // Only opaque identifiers and a one-way payload hash are persisted; no form PII is stored.
    sessionStorage.setItem(registrationAttemptStorageKey, JSON.stringify(attempt));
  } catch (_) {
    // The in-memory request still remains stable for retries in this submission.
  }
}

function clearRegistrationAttempt() {
  try {
    sessionStorage.removeItem(registrationAttemptStorageKey);
  } catch (_) {
    // Storage may be unavailable in privacy modes.
  }
}

function registrationAttemptFor(hash) {
  const pending = readRegistrationAttempt();
  if (pending?.payloadHash === hash) return pending;
  const attempt = {
    eventId,
    key: newRequestId(),
    correlationId: newRequestId(),
    payloadHash: hash,
    status: "pending",
    createdAt: new Date().toISOString(),
  };
  writeRegistrationAttempt(attempt);
  return attempt;
}

function setRegistrationState(state, message = "") {
  const form = $("#publicRegisterForm");
  const button = $("#registrationSubmitButton") || form?.querySelector("button");
  const resultBox = $("#publicResult");
  const busy = state === "submitting" || state === "recovering";
  if (form) form.setAttribute("aria-busy", busy ? "true" : "false");
  if (button) {
    button.disabled = busy;
    button.textContent = state === "recovering" ? "Verificando confirmacion..." : state === "submitting" ? "Procesando..." : state === "unknown" ? "Reintentar confirmacion" : "Inscribirme";
  }
  if (!resultBox || !message) return;
  resultBox.setAttribute("role", state === "error" || state === "conflict" ? "alert" : "status");
  const panelClass = state === "error" || state === "conflict" ? "danger" : "info";
  resultBox.innerHTML = `<div class="panel ${panelClass}">${message}</div>`;
}

function retryDelay(attemptNumber) {
  return new Promise((resolve) => setTimeout(resolve, 600 * (2 ** attemptNumber)));
}

async function submitRegistration(payload, attempt) {
  let lastError = null;
  for (let index = 0; index < REGISTRATION_MAX_ATTEMPTS; index += 1) {
    if (index > 0) {
      setRegistrationState("recovering", "La primera respuesta no llego. Estamos verificando la misma inscripcion sin duplicarla.");
      await retryDelay(index - 1);
    }
    try {
      return await api("/api/register", {
        method: "POST",
        body: JSON.stringify(payload),
        timeoutMs: REGISTRATION_TIMEOUT_MS,
        headers: {
          "Idempotency-Key": attempt.key,
          "X-Correlation-ID": attempt.correlationId,
        },
      });
    } catch (error) {
      lastError = error;
      if (!error.retryable || error.status === 409) throw error;
    }
  }
  throw lastError || new ApiError("No se pudo confirmar la inscripcion.", { code: "UNKNOWN_RESULT", retryable: true });
}

function applyAppConfig(config) {
  if (!config?.demo || document.querySelector(".demo-ribbon")) return;
  const ribbon = document.createElement("div");
  ribbon.className = "demo-ribbon";
  ribbon.textContent = "BITORA DEMO";
  document.body.appendChild(ribbon);
}

function formData(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  data.activity_ids = [];
  const communicationConsent = Boolean(form.elements.acepta_comunicaciones?.checked);
  data.acepta_email = communicationConsent;
  data.acepta_whatsapp = communicationConsent;
  data.canal_preferido = "whatsapp";
  data.source = source;
  data.source_detail = sourceDetail;
  data.device_type = deviceType();
  data.session_id = sessionId;
  data.channel = source === "whatsapp" ? "whatsapp" : "web";
  data.waiting_room_token = $("#waitingRoomToken")?.value || "";
  return data;
}

function renderWaitingRoom(status) {
  const panel = $("#waitingRoomPanel");
  const form = $("#publicRegisterForm");
  if (!status.enabled || status.status === "open" || status.status === "admitted") {
    panel.classList.add("hidden");
    form.classList.remove("hidden");
    if (status.access_token) $("#waitingRoomToken").value = status.access_token;
    if (waitingTimer) clearTimeout(waitingTimer);
    return;
  }
  panel.classList.remove("hidden");
  form.classList.add("hidden");
  $("#waitingRoomTitle").textContent = status.status === "not_open" ? "Las inscripciones abriran proximamente" : "Estas en la sala de espera";
  $("#waitingRoomMessage").textContent = status.message || "Estamos organizando el ingreso.";
  $("#waitingRoomMetrics").innerHTML = status.status === "waiting" ? `
    ${status.show_position ? `<div><strong>${status.position}</strong><span>Posicion</span></div>` : ""}
    ${status.show_estimated_time ? `<div><strong>${status.estimated_minutes} min</strong><span>Espera estimada</span></div>` : ""}
  ` : `<div><strong>${status.open_at ? new Date(status.open_at).toLocaleString() : "Proximamente"}</strong><span>Apertura</span></div>`;
  waitingTimer = setTimeout(checkWaitingRoom, 3000);
}

async function checkWaitingRoom() {
  const status = await api(`/api/waiting-room/status?event_id=${eventId}&visitor_id=${encodeURIComponent(waitingVisitorId)}`);
  renderWaitingRoom(status);
  return status;
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return `${String(date.getDate()).padStart(2, "0")} ${date.toLocaleString("es-AR", { month: "short" }).replace(".", "").toUpperCase()}`;
}

function formatTimeRange(start, end) {
  if (!start) return "-";
  const formatter = new Intl.DateTimeFormat("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false });
  const startText = formatter.format(new Date(start));
  const endText = end ? formatter.format(new Date(end)) : "";
  return endText ? `${startText} a ${endText} hs` : `${startText} hs`;
}

function renderPublicTypes(types = []) {
  const available = new Set(types.map((row) => String(row.name || "").trim().toLowerCase()));
  const preferred = [
    { value: "General", label: "Publico General", aliases: ["general", "publico general", "público general"] },
    { value: "Disertante", label: "Disertante", aliases: ["disertante", "disertantes"] },
    { value: "Prensa", label: "Prensa", aliases: ["prensa"] },
  ];
  return preferred
    .filter((row) => row.value === "General" || row.aliases.some((alias) => available.has(alias)))
    .map((row) => `<option value="${row.value}">${row.label}</option>`)
    .join("");
}

async function loadEvent() {
  if (!eventId) throw new Error("Falta evento");
  const event = await api(`/api/event?event_id=${eventId}`);
  currentEvent = event;
  applyEventTheme(event);
  document.title = event.name;
  $("#eventTitle").textContent = event.name;
  $("#eventDescription").textContent = event.description || "Completa tus datos para recibir tu credencial digital.";
  $("#eventDate").textContent = formatDate(event.starts_at);
  $("#eventTime").textContent = formatTimeRange(event.starts_at, event.ends_at);
  $("#eventVenue").textContent = event.venue || "-";
  $("#publicTypeSelect").innerHTML = renderPublicTypes(event.types) || `<option value="General">Publico General</option>`;
  $("#publicTypeSelect").value = "General";
  $("#sourceInput").value = source;
  $("#sourceDetailInput").value = sourceDetail;
  $("#deviceInput").value = deviceType();
  $("#sessionInput").value = sessionId;
  await checkWaitingRoom();
  track("landing_opened");
}

async function track(action) {
  try {
    await api("/api/captation/event", {
      method: "POST",
      body: JSON.stringify({
        event_id: eventId,
        action,
        source,
        source_detail: sourceDetail,
        device_type: deviceType(),
        session_id: sessionId,
      }),
    });
  } catch (_) {
    // La captacion no debe bloquear la inscripcion.
  }
}

async function register(event) {
  event.preventDefault();
  if (registrationSubmitting) return;
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = eventId;
  data.actor = "public";
  const resultBox = $("#publicResult");
  try {
    if (data.acepta_whatsapp && !String(data.phone || "").replace(/\D/g, "").match(/^\d{10,15}$/)) {
      throw new Error("Ingresa el telefono con codigo de pais y area para recibir WhatsApp.");
    }
    const hash = await payloadHash(data);
    const attempt = registrationAttemptFor(hash);
    if (attempt.status === "conflict") {
      throw new ApiError("Esta solicitud cambio despues de iniciarse. Revisa los datos modificados para comenzar un intento nuevo.", { status: 409, code: "IDEMPOTENCY_PAYLOAD_CONFLICT" });
    }
    registrationSubmitting = true;
    setRegistrationState("submitting", "Estamos procesando tu inscripcion. No cierres esta pagina.");
    const result = await submitRegistration(data, attempt);
    clearRegistrationAttempt();
    formStarted = false;
    const email = result.communications?.email;
    const whatsapp = result.communications?.whatsapp;
    const channelLabel = (name, channel) => {
      if (channel?.status === "sent") return `${name}: enviado.`;
      if (channel?.status === "pending") return `${name}: envio en proceso.`;
      if (channel?.status === "error") return `${name}: no pudo enviarse; la acreditacion sigue activa.`;
      return `${name}: no enviado.`;
    };
    resultBox.innerHTML = `
      <div class="panel success">
        <h2>Inscripcion confirmada</h2>
        <p>${channelLabel("Email", email)} ${channelLabel("WhatsApp", whatsapp)}</p>
        <a class="button" href="${result.portal_url}">Abrir mi portal y ver QR</a>
      </div>
    `;
    resultBox.setAttribute("role", "status");
    form.reset();
    setTimeout(() => { location.href = result.portal_url; }, 3500);
  } catch (err) {
    const pending = readRegistrationAttempt();
    if (err.code === "REGISTRATION_IDEMPOTENCY_CONFLICT") {
      if (pending) writeRegistrationAttempt({ ...pending, status: "conflict" });
      setRegistrationState("conflict", "No pudimos reutilizar este intento porque los datos no coinciden. Revisa o modifica el formulario antes de volver a enviarlo.");
    } else if (err.retryable) {
      setRegistrationState("unknown", "No recibimos la confirmacion final. La solicitud puede haberse procesado; usa Reintentar confirmacion para verificarla sin duplicarla.");
    } else {
      clearRegistrationAttempt();
      setRegistrationState("error", err.message || "No se pudo completar la inscripcion.");
    }
  } finally {
    registrationSubmitting = false;
    const state = readRegistrationAttempt()?.status === "conflict" ? "conflict" : "idle";
    const button = $("#registrationSubmitButton") || form.querySelector("button");
    form.setAttribute("aria-busy", "false");
    if (button) {
      button.disabled = false;
      if (state !== "conflict") button.textContent = readRegistrationAttempt() ? "Reintentar confirmacion" : "Inscribirme";
    }
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  $("#publicRegisterForm").addEventListener("submit", register);
  $("#publicRegisterForm").addEventListener("input", () => {
    if (formStarted) return;
    formStarted = true;
    track("form_started");
  });
  window.addEventListener("beforeunload", () => {
    if (formStarted) {
      navigator.sendBeacon?.("/api/captation/event", JSON.stringify({
        event_id: eventId,
        action: "form_abandoned",
        source,
        source_detail: sourceDetail,
        device_type: deviceType(),
        session_id: sessionId,
      }));
    }
    if ($("#waitingRoomPanel") && !$("#waitingRoomPanel").classList.contains("hidden")) {
      navigator.sendBeacon?.("/api/waiting-room/abandon", JSON.stringify({ event_id: eventId, visitor_id: waitingVisitorId }));
    }
  });
  try {
    applyAppConfig(await api("/api/app-config"));
    await loadEvent();
  } catch (err) {
    $(".public-page").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
});
