# BITORA V4.0.0 Release Notes

Fecha: 2026-08-04

## Estado

BITORA V4.0.0 queda publicada como cierre funcional V4 con Endurance 24h diferido a un prompt posterior.

No se declara certificacion operativa sostenida de 24 horas.

## Incluye

- V4.1 Attendance Domain.
- V4.2 Attendance Closure and Eligibility.
- V4.3 Certificates Foundation.
- V4.4 Surveys Foundation.
- V4.5 Speakers Foundation.
- V4.6 Zone Permissions Foundation.
- V4.7 History and Autocomplete Foundation.
- V4.8 Operations Center.
- V4.9 Communications Automation.
- V4.10 Analytics and Functional Closure.

## Validaciones

- Security: PASSED.
- Multitenant isolation: PASSED.
- Multievent isolation: PASSED.
- Backup/Restore: PASSED.
- Email Live: PASSED.
- Google OAuth Live: PASSED.
- WhatsApp Live desde BITORA: PASSED.
- Meta WhatsApp webhook real: PASSED.
- Firma de webhook: PASSED.
- Tenant resolution: PASSED.
- Auditoria: PASSED.
- Idempotencia: PASSED.
- Secretos expuestos: 0.
- Comunicaciones reales no autorizadas: 0.

## BSTF

- Score: 82.6/100.
- Gates PASSED: 46.
- Gate diferido: `endurance_24h`.

## Politica operativa

- Safe Mode debe permanecer ON.
- Live Mode debe permanecer OFF salvo autorizacion humana expresa.
- PostgreSQL es obligatorio para staging y produccion.
- SQLite queda permitido solo para local/demo.
- Produccion requiere credenciales, recursos, backup y autorizacion humana.

## Limitacion principal

`endurance_24h` queda diferido. Debe ejecutarse antes de declarar certificacion operativa sostenida.
