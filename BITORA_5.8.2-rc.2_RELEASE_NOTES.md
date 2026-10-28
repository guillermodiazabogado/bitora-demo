# BITORA 5.8.2-rc.2

Candidata local de preparación operativa basada en el SHA certificado `8985301`.

## Cambios

- Pillow actualizado de 12.3.0 a 13.0.0 para resolver 38 vulnerabilidades reportadas por pip-audit/OSV.
- Staging local aislado con PostgreSQL 16, dos instancias y balanceador.
- Harness de backup/restore con checksum y medición RPO/RTO observada.
- Harness multiinstancia con sesiones, revocación, anti-passback, idempotencia y endurance HTTP/PostgreSQL.
- Monitor reproducible de health, readiness, latencia y recursos.
- Escaneo OSV de lock y Trivy de imagen reproducible.

## Estado

No publicada ni autorizada para producción. La ejecución integrada permanece condicionada a un daemon Docker funcional o a infraestructura de CI autorizada.

