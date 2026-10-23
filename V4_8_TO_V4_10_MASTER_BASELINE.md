# BITORA V4.8-V4.10 Master Baseline

Fecha: 2026-07-29
Rama inicial: `develop/v4`
HEAD validado: `db8079eff8b673541a21b048812395414b0111f4`
Working tree: limpio antes de iniciar

## Estado heredado

V4.1 Attendance, V4.2 Closure & Eligibility, V4.3 Certificates, V4.4 Surveys,
V4.5 Speakers, V4.6 Zone Permissions y V4.7 History & Autocomplete están
verificados en la base actual. También pasaron seguridad básica, aislamiento de
20 eventos, integridad, convivencia de módulos, restore de evento, BDF migrate,
health, smoke-test y los verificadores de backup/restore existentes.

## Infraestructura y datos

- SQLite sigue siendo el runtime de verificación local; PostgreSQL/BDF conserva
  el camino operativo de staging.
- Las migraciones existentes están aplicadas y el health check está saludable.
- Storage y backups permanecen separados y protegidos por el flujo existente.
- Las colas y workers existentes no se modifican durante la baseline.

## Restricciones de esta secuencia

- No se ejecuta Endurance 24h, piloto real ni certificación final.
- Email y WhatsApp permanecen en Safe Mode; no se envían comunicaciones reales.
- No se incorporan secretos al repositorio.
- Toda nueva versión tendrá rama, flag, migración, verificador, documentación,
  commit y revisión propios.
- Una puerta fallida bloquea la siguiente versión.

## Dependencias y riesgos

- Operations Center debe consumir los dominios existentes sin convertirse en
  fuente primaria.
- Communications & Automation debe conservar la protección de envíos, el
  consentimiento, la idempotencia y la separación por organización/evento.
- Analytics debe derivar métricas de fuentes conocidas, respetar privacidad y
  no mezclar eventos, organizaciones ni Safe Mode con Live Mode.
- Nuevas tablas y artefactos persistentes deberán integrarse a backup/restore.

## Resultado de la puerta de entrada

La base está habilitada para iniciar V4.8. El estado de Release estable y
Endurance permanece sin cambios y no certificado.
