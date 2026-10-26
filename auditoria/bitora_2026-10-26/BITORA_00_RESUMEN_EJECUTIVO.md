# BITORA — Resumen ejecutivo de auditoría

Fecha: 2026-10-26  
Rama: `deployment/v4-online`  
Commit: `1dc025ab15a529ade17d3dda740d7dfb296c49b9`

## Dictamen

BITORA contiene un core funcional amplio y una implementación enterprise sustancial, pero el estado auditado no puede considerarse preparado para producción enterprise.

No se clasificó ningún módulo como **OPERATIVA VERIFICADA** porque no fue posible ejecutar la suite Python sobre el HEAD actual, no se certificó PostgreSQL/R2 ni infraestructura multiinstancia y los resultados V5 disponibles pertenecen a evidencia histórica local no versionada.

El principal bloqueo funcional es el control de accesos: el endpoint QR principal conserva la decisión V4 y ejecuta el Access State Engine V5.1 posteriormente, en modo shadow. Por ello anti-passback, cooldown, estados OUTSIDE/INSIDE e idempotencia V5 no gobiernan la operación principal.

V5.2–V5.6 y V5.8 poseen tablas y servicios internos, pero carecen de contratos API productivos e interfaces operativas completas. Command Center V5.7 sí tiene endpoint y pantalla conectada a datos reales, aunque no fue validado actualmente, no refresca automáticamente y parte de su health es constante.

## Tabla general

| Módulo | Estado | Evidencia | Riesgo | Acción necesaria |
|---|---|---|---|---|
| Eventos, inscripción y participantes | IMPLEMENTADA SIN VALIDACIÓN | Backend, UI y persistencia presentes | Medio | E2E actual sobre HEAD |
| Portal, credencial y QR | IMPLEMENTADA SIN VALIDACIÓN | Servicios QR y páginas públicas | Alto | Probar aislamiento y replay |
| Acreditación V4 | PARCIAL | `/api/validate` conectado | Crítico | Integrar autoridad V5 |
| Access State Engine V5.1 | PARCIAL | Motor implementado, solo shadow | Crítico | Enforced transaccional |
| Certificados y encuestas | IMPLEMENTADA SIN VALIDACIÓN | Servicios y migraciones | Medio/Alto | Revalidar generación, privacidad y restore |
| Networking | IMPLEMENTADA SIN VALIDACIÓN | Servicio y páginas dedicadas | Medio | Pruebas de permisos y privacidad |
| Comunicaciones | PARCIAL/BLOQUEADA | Demo y proveedores configurables | Alto | Certificación con proveedores reales |
| Delegaciones V5.3 | PARCIAL | Servicio interno | Alto | API y UI autenticadas |
| Vouchers V5.4 | PARCIAL | Servicio interno | Alto | API, UI y concurrencia offline |
| Leads V5.5 | PARCIAL | Servicio interno | Alto | API/UI y validación de consentimiento |
| Vehículos V5.6 | PARCIAL | Servicio interno | Alto | API/UI y pruebas de gates |
| Command Center V5.7 | IMPLEMENTADA SIN VALIDACIÓN | Endpoint y UI reales | Alto | Health real, refresh y E2E |
| Device/Edge V5.2/V5.8 | PARCIAL/BLOQUEADA | Backend sin cliente ni API | Alto | Contrato operativo y cliente Edge |
| PostgreSQL | IMPLEMENTADA SIN VALIDACIÓN | Pool y adaptador | Alto | Certificar migraciones y compatibilidad |
| Producción enterprise | NO VERIFICABLE | Sin validación actual de entorno | Crítico | Completar P0/P1 y recertificar |

## Respuesta ejecutiva

- La identidad de versión es incoherente: Git describe evolución posterior a V4, el servidor declara `RC1-live-demo-10` y existen componentes hasta V5.8.
- El core V1–V4 es utilizable como base de desarrollo, pero no posee certificación actual reproducible.
- Los módulos enterprise no deben ofrecerse como terminados hasta disponer de API, UI/cliente y pruebas E2E.
- La madurez funcional es mayor que la madurez operativa, de seguridad y de producción.
- La prioridad inmediata es unificar la autoridad de accesos, cerrar el aislamiento multievento y certificar el esquema contra PostgreSQL.
