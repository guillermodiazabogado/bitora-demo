# Informe final — BITORA 5.8.2-rc.1

## Software desarrollado e integrado

- Sesiones persistentes aptas para múltiples procesos, sin tokens en claro.
- Aislamiento de Leads por compañía y consentimiento endurecido.
- Cliente Edge de referencia con cola durable y reconciliación.
- Interfaces conectadas de Vouchers, Leads y Vehículos.
- Command Center resiliente ante desconexión y datos vencidos, con Fit/Zoom/Layers y vista visual/tabla funcionales.
- Docker reproducible/no-root, restore aislado y CI de releases.

## Software probado localmente

- 33 gates de regresión y seguridad: PASS.
- Concurrencia de accesos: 30 ENTRY, 1 ALLOW, 29 anti-passback.
- Multievento: 20 eventos y 1000 participantes aislados.
- Edge: 100 operaciones offline conservadas tras restart y sincronizadas 100/100.
- Auth HTTP: login, upgrade Argon2id, CSRF, cookie segura y rate limit.
- Leads/Vehículos: integración SQLite real temporal e integridad final `ok`.

## No certificado todavía sobre esta RC

- PostgreSQL 16 con migración 049.
- Docker build/run efectivo de la imagen RC.
- E2E Linux CI, SBOM y artefactos ligados al commit RC.
- Staging, multiinstancia, hardware, cámaras, red física y proveedores externos.
- Restore drill real y endurance integrada HTTP/PostgreSQL.

La RC queda lista para evaluación de staging, no autorizada para producción.
