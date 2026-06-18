CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    venue TEXT NOT NULL DEFAULT '',
    starts_at TEXT NOT NULL DEFAULT '',
    ends_at TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    capacity INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    activity_selection_mode TEXT NOT NULL DEFAULT 'optional_later',
    permitir_reserva_actividades_desde_landing INTEGER NOT NULL DEFAULT 0,
    permitir_reserva_actividades_desde_portal INTEGER NOT NULL DEFAULT 1,
    reserva_requiere_confirmacion INTEGER NOT NULL DEFAULT 1,
    reserva_cooldown_segundos INTEGER NOT NULL DEFAULT 5,
    reserva_requiere_verificacion_simple INTEGER NOT NULL DEFAULT 1,
    generar_certificados INTEGER NOT NULL DEFAULT 1,
    controlar_asistencia INTEGER NOT NULL DEFAULT 1,
    attendance_mode TEXT NOT NULL DEFAULT 'entry_only',
    porcentaje_minimo_asistencia INTEGER NOT NULL DEFAULT 80,
    captation_mode TEXT NOT NULL DEFAULT 'MIXTO',
    primary_action_label TEXT NOT NULL DEFAULT '',
    secondary_action_label TEXT NOT NULL DEFAULT '',
    whatsapp_number TEXT NOT NULL DEFAULT '',
    activity_access_open_minutes_before INTEGER NOT NULL DEFAULT 10,
    activities_enabled INTEGER NOT NULL DEFAULT 1,
    capacity_control_enabled INTEGER NOT NULL DEFAULT 1,
    waitlist_enabled INTEGER NOT NULL DEFAULT 0,
    landing_image_data TEXT NOT NULL DEFAULT '',
    landing_image_name TEXT NOT NULL DEFAULT '',
    landing_image_type TEXT NOT NULL DEFAULT '',
    landing_image_updated_at TEXT NOT NULL DEFAULT '',
    landing_logo_data TEXT NOT NULL DEFAULT '',
    landing_primary_color TEXT NOT NULL DEFAULT '',
    landing_secondary_color TEXT NOT NULL DEFAULT '',
    landing_mobile_banner_data TEXT NOT NULL DEFAULT '',
    landing_video_url TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS people (
    id BIGSERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL DEFAULT '',
    dni TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    position TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    device_type TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    pin_hash TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS accreditations (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    type TEXT NOT NULL DEFAULT 'General',
    token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    checked_in_at TEXT,
    checked_in_by TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    max_reentries INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    requiere_asistencia INTEGER NOT NULL DEFAULT 0,
    porcentaje_minimo INTEGER NOT NULL DEFAULT 0,
    elegible_certificado INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT '',
    source_detail TEXT NOT NULL DEFAULT '',
    device_type TEXT NOT NULL DEFAULT '',
    UNIQUE(event_id, person_id)
);

CREATE TABLE IF NOT EXISTS accreditation_types (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    access_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(event_id, name)
);

CREATE TABLE IF NOT EXISTS spaces (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    responsible TEXT NOT NULL DEFAULT '',
    transition_minutes INTEGER NOT NULL DEFAULT 15,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    UNIQUE(event_id, name)
);

CREATE TABLE IF NOT EXISTS activities (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    space_id BIGINT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    speaker TEXT NOT NULL DEFAULT '',
    activity_type TEXT NOT NULL DEFAULT 'Charla',
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    reservation_mode TEXT NOT NULL DEFAULT 'free',
    status TEXT NOT NULL DEFAULT 'published',
    created_at TEXT NOT NULL,
    requiere_asistencia INTEGER NOT NULL DEFAULT 1,
    porcentaje_minimo_asistencia INTEGER NOT NULL DEFAULT 80,
    habilita_certificado INTEGER NOT NULL DEFAULT 1,
    attendance_mode TEXT NOT NULL DEFAULT '',
    access_open_minutes_before INTEGER
);

CREATE TABLE IF NOT EXISTS capacity_bags (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    assigned_capacity INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 100,
    public_visible INTEGER NOT NULL DEFAULT 0,
    public_registration INTEGER NOT NULL DEFAULT 0,
    reception_enabled INTEGER NOT NULL DEFAULT 1,
    release_enabled INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    UNIQUE(activity_id, code)
);

CREATE TABLE IF NOT EXISTS reservations (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL,
    bag_id BIGINT REFERENCES capacity_bags(id) ON DELETE SET NULL,
    UNIQUE(activity_id, accreditation_id)
);

CREATE TABLE IF NOT EXISTS public_display_config (
    event_id BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'airport',
    refresh_seconds INTEGER NOT NULL DEFAULT 10,
    paused INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    room_filter TEXT NOT NULL DEFAULT '',
    status_filter TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS public_display_items (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    visible INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(event_id, activity_id)
);

CREATE TABLE IF NOT EXISTS access_logs (
    id BIGSERIAL PRIMARY KEY,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    event_id BIGINT REFERENCES events(id) ON DELETE SET NULL,
    token TEXT NOT NULL,
    operator TEXT NOT NULL DEFAULT '',
    checkpoint TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    operator_id BIGINT,
    access_point TEXT NOT NULL DEFAULT '',
    access_context TEXT NOT NULL DEFAULT 'event_entry'
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id BIGINT,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS participant_communication_preferences (
    id BIGSERIAL PRIMARY KEY,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE UNIQUE,
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    acepta_email INTEGER NOT NULL DEFAULT 0,
    acepta_whatsapp INTEGER NOT NULL DEFAULT 0,
    canal_preferido TEXT NOT NULL DEFAULT 'email',
    fecha_consentimiento TEXT,
    ultimo_contacto TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_logs (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    canal TEXT NOT NULL,
    fecha TEXT NOT NULL,
    tipo TEXT NOT NULL,
    asunto TEXT NOT NULL DEFAULT '',
    contenido TEXT NOT NULL DEFAULT '',
    estado TEXT NOT NULL DEFAULT 'demo'
);

CREATE TABLE IF NOT EXISTS communication_queue (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    channel TEXT NOT NULL,
    audience TEXT NOT NULL DEFAULT '',
    template_code TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    recipient TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pendiente',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    provider TEXT NOT NULL DEFAULT 'demo',
    provider_message_id TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    scheduled_at TEXT,
    processed_at TEXT,
    delivered_at TEXT,
    bounced_at TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_delivery_events (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    queue_id BIGINT REFERENCES communication_queue(id) ON DELETE SET NULL,
    provider TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_assistant_history (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    phone TEXT NOT NULL DEFAULT '',
    inbound TEXT NOT NULL DEFAULT '',
    outbound TEXT NOT NULL DEFAULT '',
    intent TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'resolved',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_tickets (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    channel TEXT NOT NULL DEFAULT 'whatsapp',
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_templates (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL DEFAULT 0,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    tipo TEXT NOT NULL,
    asunto TEXT NOT NULL DEFAULT '',
    contenido TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(event_id, code)
);

CREATE TABLE IF NOT EXISTS participant_announcements (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'published',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS captation_events (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT 'landing',
    source_detail TEXT NOT NULL DEFAULT '',
    device_type TEXT NOT NULL DEFAULT 'desktop',
    action TEXT NOT NULL,
    session_id TEXT NOT NULL DEFAULT '',
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_sources (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    source TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    device_type TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_attendance (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    reservation_id BIGINT REFERENCES reservations(id) ON DELETE SET NULL,
    entry_at TEXT,
    entry_operator TEXT NOT NULL DEFAULT '',
    exit_at TEXT,
    exit_operator TEXT NOT NULL DEFAULT '',
    attended_minutes INTEGER NOT NULL DEFAULT 0,
    attendance_percentage INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Pendiente',
    eligibility_status TEXT NOT NULL DEFAULT 'Pendiente',
    corrected_by TEXT NOT NULL DEFAULT '',
    correction_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(activity_id, accreditation_id)
);

CREATE TABLE IF NOT EXISTS certificate_eligibility (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    porcentaje INTEGER NOT NULL DEFAULT 0,
    elegible INTEGER NOT NULL DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'Pendiente',
    fecha_calculo TEXT NOT NULL,
    certificate_generated_at TEXT,
    UNIQUE(activity_id, accreditation_id)
);
