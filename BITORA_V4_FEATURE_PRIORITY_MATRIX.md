# BITORA V4 Feature Priority Matrix

| Funcionalidad | Prioridad | Valor | Costo | Riesgo | Dependencias | Impacto Certificacion |
|---|---|---|---|---|---|---|
| Asistencia real | P0 | Alto | Medio | Alto | QR, actividades, auditoria | Seguridad, aislamiento, backup, restore |
| Cierre de asistencia | P0 | Alto | Medio | Alto | Asistencia | Auditoria, jobs, upgrade |
| Certificados | P0 | Alto | Medio | Alto | Asistencia, storage | Storage, comunicaciones, backup |
| Encuestas | P0 | Medio | Medio | Medio | Participantes, portal | Privacidad, exportaciones |
| Disertantes | P0 | Medio | Medio | Medio | Usuarios, actividades, storage | RBAC, multitenant |
| Permisos por zonas | P0 | Alto | Alto | Alto | QR, accesos, roles | Seguridad, aislamiento |
| Historial participante | P0 | Alto | Medio | Alto | People, eventos | Privacidad, multitenant |
| Autocompletado | P0 | Medio | Medio | Alto | Historial, consentimiento | Privacidad |
| Panel operativo | P0 | Alto | Medio | Medio | Reportes, jobs | UI, permisos |
| Incidencias | P0 | Medio | Medio | Medio | Usuarios, auditoria | Auditoria |
| Estado de salas | P0 | Medio | Bajo | Medio | Actividades, incidencias | Operacion |
| Exportaciones finales | P0 | Alto | Bajo | Medio | Reportes | Datos personales |
| Agenda personalizada | P1 | Medio | Medio | Medio | Reservas, portal | UI |
| Credencial digital | P1 | Alto | Medio | Alto | QR, portal, storage | Seguridad |
| Comunicaciones reales ampliadas | P1 | Alto | Medio | Alto | Integraciones certificadas | Email/WhatsApp |
| Recordatorios | P1 | Alto | Medio | Alto | Automatizaciones, jobs | Safe Mode |
| Dashboard ejecutivo | P1 | Medio | Medio | Medio | Analytics | Reportes |
| KPIs | P1 | Medio | Medio | Medio | Snapshots | Consistencia |
| Acciones masivas | P1 | Alto | Medio | Alto | Permisos, auditoria | Seguridad |
| Conciliacion de cupos | P1 | Medio | Medio | Medio | Reservas | Integridad |
| Reportes avanzados | P1 | Medio | Medio | Medio | Analytics | Exportacion |
| Automatizaciones configurables | P2 | Medio | Alto | Alto | Jobs, eventos dominio | Jobs, DR |
| Calendarios | P2 | Medio | Medio | Alto | Google OAuth | Google live |
| CRM | P2 | Medio | Alto | Alto | API futura | Integraciones |
| Mercado Pago | P2 | Medio | Alto | Alto | Pagos, webhooks | Seguridad |
| Streaming | P2 | Bajo | Alto | Medio | Proveedor externo | Integracion |
| API publica | P2 | Alto | Alto | Alto | Contratos v1 | Seguridad |
| IA autonoma | P3 | Bajo hoy | Alto | Muy alto | Datos y reglas | No MVP |
| Reconocimiento facial | P3 | Bajo hoy | Alto | Muy alto | Consentimiento biometrico | No MVP |

## Regla

P0 define el MVP. P1 se evalua despues de estabilizar P0. P2 requiere aprobacion explicita. P3 queda fuera.
