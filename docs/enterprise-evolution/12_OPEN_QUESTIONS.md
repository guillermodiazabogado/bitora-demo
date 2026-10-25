# BITORA V5 Discovery - Open Questions

Solo preguntas que requieren decision humana/producto.

1. Que prioridad comercial tiene V5: accesos enterprise, delegaciones, command center o lead retrieval?
2. Se usara BITORA en eventos con operacion sin internet real? Si si, cuanto tiempo offline debe tolerar?
3. Habra dispositivos propios provistos por BITORA o dispositivos del cliente?
4. El primer piloto enterprise tendra zonas/puertas fisicas reales o solo simulacion?
5. Las empresas/sponsors deben autogestionar invitados desde V5.3 o alcanza carga operativa interna?
6. Se requiere dominio propio para emails productivos antes de cerrar V4 operativo?
7. Que datos personales sensibles se permitiran almacenar: foto, documento, patente, biometria?
8. El command center debe ser tiempo real estricto o refresco cada pocos segundos alcanza?
9. Cashless queda fuera de V5 inicial? Recomendacion tecnica: si, dejarlo FUTURE.
10. Que hardware concreto se quiere probar primero: impresora, lector QR, NFC/RFID, terminal tactil o camara?

## ExecPlans Propuestos

### ExecPlan 1 - V5.0 Enterprise Core Shadow Model

Goal: disenar e implementar modelo aditivo Entity/Entitlement/Rule en shadow mode.
Scope: nuevas tablas aditivas, servicios de lectura/escritura controlados, tests unitarios, backup/restore.
Out of Scope: cambiar /api/validate, hardware, offline.
Dependencies: baseline V4 aprobada, feature flags.
Files likely affected: backend/migrations, backend/services, tests/verificadores, backup.
Database impact: aditivo.
API impact: ninguno publico al inicio.
Migration: nueva migracion no destructiva.
Rollback: feature flag OFF.
Tests: schema, backup/restore, multitenant, no regression.
Acceptance Criteria: shadow model no cambia runtime V4.
Risks: duplicar conceptos con people/accreditations.
Observability: audit + counts.
No Regression Checks: V4 full gate.

### ExecPlan 2 - Access State Engine Shadow

Goal: calcular decision V5 paralela a decision V4.
Scope: IN/OUT, cooldown, revocation, zone shadow.
Out of Scope: enforcement por defecto.
Dependencies: ExecPlan 1.
Database impact: access events append-only.
API impact: opcional endpoint debug admin.
Rollback: apagar shadow.
Tests: comparador V4/V5.
Acceptance Criteria: no altera acceso real.

### ExecPlan 3 - Device Identity Foundation

Goal: registrar terminales/dispositivos y asociar operaciones.
Scope: device registry, token de dispositivo, last_seen, dataset revision.
Out of Scope: drivers de hardware.
Dependencies: Access State Engine.
Rollback: aceptar operaciones sin device en modo legacy.
Tests: auth device, audit, backup.

### ExecPlan 4 - Email Production Closure

Goal: dejar comunicaciones email realmente operativas.
Scope: dominio Resend verificado, Railway vars, webhook, prueba delivered.
Out of Scope: campañas masivas.
Dependencies: dominio propio/DNS.
Database impact: ninguno esperado.
Acceptance Criteria: provider_message_id + delivered webhook + historial.
