# BITORA — Integración, documentación y trazabilidad

## Fuentes evaluadas

- Código backend y frontend.
- Migraciones SQL.
- Configuración y despliegue.
- Scripts de verificación.
- Informes históricos y artefactos endurance.
- Documentación V4 y `docs/enterprise-evolution/`.

## Matriz de trazabilidad

| Requerimiento | Implementación | Prueba conservada | Integración actual | Estado |
|---|---|---|---|---|
| V5.1 Access State | Servicio y migración | Script directo histórico | Shadow en `/api/validate` | PARCIAL |
| V5.2 Device/Edge | Servicio y tablas | Script directo histórico | Sin API/cliente | PARCIAL |
| V5.3 Delegaciones | Servicio y tablas | Script directo histórico | Sin API/UI | PARCIAL |
| V5.4 Vouchers | Servicio y tablas | Script directo histórico | Sin API/UI | PARCIAL |
| V5.5 Leads | Servicio y tablas | Script directo histórico | Sin API/UI | PARCIAL |
| V5.6 Vehículos | Servicio y tablas | Script directo histórico | Sin API/UI | PARCIAL |
| V5.7 Command Center | Servicio, migración, endpoint y UI | Script/JSON histórico | Integrado detrás de flags | IMPLEMENTADA SIN VALIDACIÓN |
| V5.7.1 Venue Map | Servicio, migración y UI | Capturas/scripts históricos | Integración parcial | PARCIAL |
| V5.8 Event Edge | Servicio y migración | Script histórico | Sin contrato productivo | PARCIAL |

## Contradicciones documentales

- Git: `v4.0.0-69-g1dc025a-dirty`.
- Rama: `deployment/v4-online`.
- App: `RC1-live-demo-10`.
- Código: componentes hasta V5.8.
- Algunos documentos declaran Release Candidate enterprise mientras otros reconocen PostgreSQL/R2 production-like no verificados.

La documentación histórica debe tratarse como antecedente. La carpeta enterprise no está versionada en el estado auditado, por lo que no establece trazabilidad confiable con el commit.

## Instalación y actualización

Existen Dockerfiles, `render.yaml`, Procfile y guías operativas. La preparación de despliegue no fue ejecutada. Falta una comprobación automatizada de versión, migraciones esperadas, dependencias, storage, worker y compatibilidad de upgrade.
