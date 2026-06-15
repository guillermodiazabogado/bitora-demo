const $ = (selector) => document.querySelector(selector);
const params = new URLSearchParams(location.search);
const eventId = Number(params.get("event_id") || 0);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Error inesperado");
  return data;
}

function formData(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  data.activity_ids = [...form.querySelectorAll('input[name="activity_ids"]:checked')].map((input) => input.value);
  return data;
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

async function loadEvent() {
  if (!eventId) throw new Error("Falta evento");
  const event = await api(`/api/event?event_id=${eventId}`);
  document.title = event.name;
  $("#eventTitle").textContent = event.name;
  $("#eventDescription").textContent = event.description || "Completa tus datos para recibir tu credencial digital.";
  $("#eventDate").textContent = `${formatDate(event.starts_at)}${event.ends_at ? ` - ${formatDate(event.ends_at)}` : ""}`;
  $("#eventVenue").textContent = event.venue || "-";
  $("#eventCapacity").textContent = "Segun disponibilidad";
  $("#publicTypeSelect").innerHTML = (event.types || []).map((row) => `<option>${row.name}</option>`).join("") || "<option>General</option>";
  const reservable = (event.activities || []).filter((row) => ["optional", "required"].includes(row.reservation_mode));
  $("#publicActivityChoices").innerHTML = reservable.map((row) => `
    <label class="activity-choice">
      <input type="checkbox" name="activity_ids" value="${row.id}">
      <span>
        <strong>${row.title}</strong>
        <small>${formatDate(row.starts_at)} - ${row.space_name || ""} - ${row.public_availability || ""}</small>
      </span>
    </label>
  `).join("") || `<p class="empty">No hay actividades con reserva publica.</p>`;
  $("#publicAgenda").innerHTML = (event.activities || []).map((row) => `
    <article class="activity-row public-activity">
      <time>${formatDate(row.starts_at)}</time>
      <div>
        <strong>${row.title}</strong>
        <span>${row.space_name || ""} - ${row.activity_type || ""} - ${row.public_availability || ""}</span>
      </div>
    </article>
  `).join("") || `<p class="empty">Agenda pendiente de publicacion.</p>`;
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
    resultBox.innerHTML = `
      <div class="panel success">
        <h2>Inscripcion confirmada</h2>
        <p>Tu credencial digital ya esta lista.</p>
        ${renderReservationResult(result.reservations || [])}
        <a class="button" href="${result.portal_url}">Ver mi credencial</a>
      </div>
    `;
    form.reset();
  } catch (err) {
    resultBox.innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
}

function renderReservationResult(reservations) {
  if (!reservations.length) return "";
  return `
    <div class="reservation-summary">
      ${reservations.map((row) => `
        <div class="${row.ok ? row.status : "rejected"}">
          <strong>${row.title || "Actividad"}</strong>
          <span>${reservationLabel(row)}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function reservationLabel(row) {
  if (!row.ok) return row.error || "No se pudo reservar";
  if (row.status === "confirmed") return "Reserva confirmada";
  if (row.status === "waitlisted") return "Lista de espera";
  return row.status;
}

document.addEventListener("DOMContentLoaded", async () => {
  $("#publicRegisterForm").addEventListener("submit", register);
  try {
    await loadEvent();
  } catch (err) {
    $(".public-page").innerHTML = `<div class="panel danger">${err.message}</div>`;
  }
});
