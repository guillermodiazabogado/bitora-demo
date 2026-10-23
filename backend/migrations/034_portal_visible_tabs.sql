ALTER TABLE events
ADD COLUMN IF NOT EXISTS portal_visible_tabs TEXT NOT NULL DEFAULT '["inicio","qr","agenda","charlas","asistencia","encuesta","certificado","notificaciones","perfil"]';
