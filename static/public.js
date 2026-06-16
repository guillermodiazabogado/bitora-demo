const $ = (selector) => document.querySelector(selector);
const params = new URLSearchParams(location.search);
const eventId = Number(params.get("event_id") || 0);
const source = (params.get("source") || params.get("utm_source") || "landing").toLowerCase();
const sourceDetail = params.get("source_detail") || params.get("utm_campaign") || params.get("qr") || "";
const sessionId = localStorage.getItem("captation_session") || crypto.randomUUID();
localStorage.setItem("captation_session", sessionId);
let currentEvent = null;
let formStarted = false;

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
}

function deviceType() {
  const width = window.innerWidth || screen.width;
  const ua = navigator.userAgent || "";
  if (/ipad|tablet/i.test(ua) || (width >= 700 && width <= 1100 && /mobile|android/i.test(ua))) return "tablet";
  if (width < 760 || /iphone|android|mobile/i.test(ua)) return "mobile";
  return "desktop";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Error inesperado");
  return data;
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
  data.acepta_email = false;
  data.acepta_whatsapp = false;
  data.canal_preferido = "email";
  data.source = source;
  data.source_detail = sourceDetail;
  data.device_type = deviceType();
  data.session_id = sessionId;
  data.channel = source === "whatsapp" ? "whatsapp" : "web";
  return data;
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

async function loadEvent() {
  if (!eventId) throw new Error("Falta evento");
  const event = await api(`/api/event?event_id=${eventId}`);
  currentEvent = event;
  applyEventTheme(event);
  document.title = event.name;
  $("#eventTitle").textContent = event.name;
  $("#eventDescription").textContent = event.description || "Completa tus datos para recibir tu credencial digital.";
  $("#eventDate").textContent = `${formatDate(event.starts_at)}${event.ends_at ? ` - ${formatDate(event.ends_at)}` : ""}`;
  $("#eventVenue").textContent = event.venue || "-";
  $("#eventCapacity").textContent = "Segun disponibilidad";
  $("#publicTypeSelect").innerHTML = (event.types || []).map((row) => `<option>${row.name}</option>`).join("") || "<option>General</option>";
  $("#sourceInput").value = source;
  $("#sourceDetailInput").value = sourceDetail;
  $("#deviceInput").value = deviceType();
  $("#sessionInput").value = sessionId;
  renderCaptationActions(event);
  track("landing_opened");
}

function renderCaptationActions(event) {
  const mode = event.captation_mode || "MIXTO";
  const mobile = deviceType() === "mobile";
  const whatsappUrl = whatsappLink(event);
  const form = $("#publicRegisterForm");
  const box = $("#captationActions");
  const webPrimary = mode === "WEB_DIRECTA" || (mode === "MIXTO" && !mobile);
  const whatsappPrimary = mode === "WHATSAPP_PRIMERO" || (mode === "MIXTO" && mobile);
  form.classList.toggle("secondary-form", whatsappPrimary);
  const primaryLabel = event.primary_action_label || (whatsappPrimary ? "Inscribirme por WhatsApp" : "Inscribirme");
  const secondaryLabel = event.secondary_action_label || (whatsappPrimary ? "Continuar por web" : "Continuar por WhatsApp");
  box.innerHTML = `
    <h2>${whatsappPrimary ? "Inscripcion por WhatsApp" : "Inscripcion web"}</h2>
    <div class="confirmation-actions">
      ${whatsappPrimary ? `<a id="whatsappPrimary" class="button" href="${whatsappUrl}" target="_blank">${primaryLabel}</a>` : `<a class="button" href="#publicRegisterForm">${primaryLabel}</a>`}
      ${webPrimary ? `<a id="whatsappSecondary" class="button ghost" href="${whatsappUrl}" target="_blank">${secondaryLabel}</a>` : `<a class="button ghost" href="#publicRegisterForm">${secondaryLabel}</a>`}
    </div>
  `;
  $("#whatsappPrimary")?.addEventListener("click", () => track("whatsapp_clicked"));
  $("#whatsappSecondary")?.addEventListener("click", () => track("whatsapp_clicked"));
}

function whatsappLink(event) {
  const phone = String(event.whatsapp_number || "").replace(/\D/g, "");
  const text = `Hola, quiero inscribirme a ${event.name}. Link: ${location.href}`;
  return phone ? `https://wa.me/${phone}?text=${encodeURIComponent(text)}` : `https://wa.me/?text=${encodeURIComponent(text)}`;
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
  const form = event.currentTarget;
  const data = formData(form);
  data.event_id = eventId;
  data.actor = "public";
  const resultBox = $("#publicResult");
  try {
    const result = await api("/api/register", { method: "POST", body: JSON.stringify(data) });
    formStarted = false;
    resultBox.innerHTML = `
      <div class="panel success">
        <h2>Inscripcion confirmada</h2>
        <p>Estamos abriendo tu portal personal.</p>
      </div>
    `;
    form.reset();
    location.href = result.portal_url;
  } catch (err) {
    resultBox.innerHTML = `<div class="panel danger">${err.message}</div>`;
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
  });
  try {
    applyAppConfig(await api("/api/app-config"));
    await loadEvent();
  } catch (err) {
    $(".public-page").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
});
