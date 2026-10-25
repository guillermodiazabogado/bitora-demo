ALTER TABLE events
ADD COLUMN IF NOT EXISTS registration_confirmation_subject TEXT NOT NULL DEFAULT 'Inscripcion confirmada';

ALTER TABLE events
ADD COLUMN IF NOT EXISTS registration_confirmation_message TEXT NOT NULL DEFAULT 'Hola {{nombre}}, tu inscripcion a {{evento}} fue confirmada. Tu QR y portal: {{portal_participante}}';
