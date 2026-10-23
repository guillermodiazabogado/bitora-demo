# V4.3 Migration Report

Migracion agregada:

`backend/migrations/018_v4_3_certificates_foundation.sql`

Resultado:

- Aditiva.
- Compatible con SQLite init y PostgreSQL migrations.
- No altera tablas V4.1/V4.2.
- Agrega indices de scope, estado, token y documentos.
