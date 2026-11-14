# BITORA 5.8.2 — Cierre funcional comercial

## Resultado

El recorrido comercial mínimo quedó integrado y validado localmente sobre la rama `fix/5.8.2-commercial-closure`, basada en `ae711a985474aa486f8f9280a4b3e5b8c0425b45`. No se modificaron staging, producción, proveedores, planes ni costos.

## Implementado

- Lifecycle formal de evento: cierre explícito, transaccional, auditable e idempotente.
- Persistencia de `closed_at`, `closed_by` y motivo mediante migración `054_event_commercial_closure.sql`.
- Bloqueo de nuevas inscripciones, reservas y validaciones QR online después del cierre.
- Conservación de consultas históricas y reconciliación de operaciones Edge pendientes.
- Acción administrativa de cierre en la configuración del evento.
- Integración certificado emitido → cola Gmail existente, sin envío directo desde la solicitud.
- Dedupe del primer envío, reenvío sólo con clave administrativa explícita e historial persistente.
- Acciones de encolado e historial en la pantalla de certificados.

## Reutilizado sin reescritura

- Eventos, identidad básica, categorías y cupos.
- Empresas mediante el campo de asociación existente y carga manual/CSV.
- Participantes, deduplicación, inscripciones idempotentes y QR.
- Salas, charlas, agenda, disertantes y reservas existentes.
- ENTRY/EXIT, asistencia por actividad, cierres de asistencia y elegibilidad.
- Plantillas versionadas, emisión individual/masiva, PDF, descarga, revocación y reemisión.
- Cola de comunicaciones y proveedor Gmail ya configurado.
- Contratos Android Operation/Display.

## Madurez del alcance afectado

| Módulo | Línea base | Estado actual | Justificación |
|---|---:|---:|---|
| Eventos — recorrido comercial | 76,4 % | 90 % | creación existente + cierre formal, auditoría, persistencia e historial funcionales; falta certificación remota |
| Programación | 77,4 % | 80 % | el recorrido manual con salas, horarios y disertantes está completo; no se agregó XLSX ni importación masiva de speakers |
| Empresas y participantes | 65,0 % | 80 % | carga manual/CSV, asociación, dedupe y persistencia cubren la demo; el portal empresarial avanzado queda fuera de alcance |
| Inscripciones | 80,7 % | 90 % | flujo completo, idempotente, QR y bloqueo posterior al cierre; certificación de producción pendiente |
| Acreditación y asistencia | 86,0 % | 90 % | QR, ENTRY/EXIT, asistencia y elegibilidad integrados; prueba física sigue pendiente |
| Certificados — recorrido comercial | 63,9 % | 90 % | elegibilidad, PDF, emisión, descarga, cola Gmail, dedupe, reenvío e historial integrados; envío real remoto no ejecutado |

La madurez del recorrido integral es **90 % funcional local**. No equivale a 100 % ni a certificación de staging/producción.

## Pruebas ejecutadas

- `verificar_commercial_closure_e2e.py`: PASS. Escenario sintético EXPO PATAGONIA 2027 con 5 empresas, 20 participantes, 5 charlas, 3 disertantes, asistencia, cierre, certificado, cola Gmail y recuperación tras reconexión.
- `verificar_p0_registration_idempotency.py`: PASS.
- `verificar_v4_1_attendance_domain.py`: PASS.
- `verificar_v4_2_attendance_closure_eligibility.py`: PASS.
- `verificar_v4_3_certificates_foundation.py`: PASS.
- `verificar_android_production_edge.py`: PASS.
- Migración 054 aplicada dos veces sobre PostgreSQL 16 efímero: PASS.
- Compilación Python, sintaxis JavaScript y `git diff --check`: PASS.

Las comunicaciones se validaron como **encolamiento seguro**; no se enviaron emails ni WhatsApp reales.

## Pendientes y límites

- Aplicar migración 054 y desplegar el candidato en staging requiere autorización específica.
- Ejecutar allí el checklist con datos ficticios y un destinatario autorizado.
- Certificar entrega Gmail real, Android físico y operación presencial por separado.
- Webhook auténtico de Meta continúa pendiente y no bloquea el certificado por Gmail.
- Producción permanece intacta y NO-GO para estos cambios.

