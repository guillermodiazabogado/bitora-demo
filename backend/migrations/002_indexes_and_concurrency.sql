CREATE INDEX IF NOT EXISTS idx_people_email_lower ON people (LOWER(email));
CREATE INDEX IF NOT EXISTS idx_people_dni ON people (dni);
CREATE INDEX IF NOT EXISTS idx_people_name_lower ON people (LOWER(last_name), LOWER(first_name));
CREATE INDEX IF NOT EXISTS idx_people_company_lower ON people (LOWER(company));
CREATE INDEX IF NOT EXISTS idx_people_phone ON people (phone);

CREATE INDEX IF NOT EXISTS idx_accreditations_event_status ON accreditations (event_id, status);
CREATE INDEX IF NOT EXISTS idx_accreditations_event_type ON accreditations (event_id, type);
CREATE INDEX IF NOT EXISTS idx_accreditations_person ON accreditations (person_id);
CREATE INDEX IF NOT EXISTS idx_accreditations_token ON accreditations (token);

CREATE INDEX IF NOT EXISTS idx_activities_event_start ON activities (event_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_activities_space_start ON activities (space_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_reservations_event_status ON reservations (event_id, status);
CREATE INDEX IF NOT EXISTS idx_reservations_activity_status ON reservations (activity_id, status);
CREATE INDEX IF NOT EXISTS idx_reservations_accreditation ON reservations (accreditation_id);
CREATE INDEX IF NOT EXISTS idx_capacity_bags_activity_status ON capacity_bags (activity_id, status, priority);

CREATE INDEX IF NOT EXISTS idx_access_logs_event_created ON access_logs (event_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_logs_token ON access_logs (token);
CREATE INDEX IF NOT EXISTS idx_access_logs_activity_context ON access_logs (activity_id, accreditation_id, access_context, result);
CREATE INDEX IF NOT EXISTS idx_access_logs_operator_created ON access_logs (operator, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_activity_granted_access
    ON access_logs (activity_id, accreditation_id, access_context)
    WHERE activity_id IS NOT NULL AND result = 'granted' AND access_context = 'activity_entry';

CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_communication_logs_event ON communication_logs (event_id, fecha);
CREATE INDEX IF NOT EXISTS idx_communication_queue_event_status ON communication_queue (event_id, status);
CREATE INDEX IF NOT EXISTS idx_communication_assistant_event ON communication_assistant_history (event_id, created_at);
CREATE INDEX IF NOT EXISTS idx_communication_tickets_event_status ON communication_tickets (event_id, status);
CREATE INDEX IF NOT EXISTS idx_attendance_event_activity ON activity_attendance (event_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_attendance_accreditation ON activity_attendance (accreditation_id);
CREATE INDEX IF NOT EXISTS idx_certificate_event ON certificate_eligibility (event_id, estado);
CREATE INDEX IF NOT EXISTS idx_captation_event_source ON captation_events (event_id, source, action);
CREATE INDEX IF NOT EXISTS idx_conversation_source_event ON conversation_sources (event_id, source);
