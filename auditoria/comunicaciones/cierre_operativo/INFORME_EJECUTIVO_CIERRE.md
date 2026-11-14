# BITORA 5.8.2 - Cierre operativo Gmail + WhatsApp + Railway + Android

Fecha: 2026-11-14
Estado: **STAGING LISTO PARA PRUEBAS REALES / WEBHOOK META EXTERNO BLOCKED**

## Despliegue

- Rama: `fix/5.8.2-whatsapp-traceability-idempotency`.
- SHA fuente autorizado: `06408c96fdc0dab59a101ff85ec1b8849c0b10c6`.
- El paquete desplegado se genero exclusivamente con `git archive` del SHA anterior; no incluyo los commits documentales posteriores.
- Proyecto Railway: `bitora-582-staging`; entorno `staging`; servicio `bitora-web`.
- URL: <https://bitora-web-staging.up.railway.app>.
- Deployment: `fed0d7d9-ca36-4a15-9fcf-a66c15c897d0` — `SUCCESS`.
- Digest: `sha256:b11984276ca20e94569477c7a3250c8a0e9e04b7a9406dfe495ca3625ab41623`.
- Dos instancias: `RUNNING / RUNNING`.
- Rollback preparado al deployment anterior `72cfa30f-33c1-4217-8940-d2f5dcb50ab9`.

## Resultado tecnico

- `/ready`: HTTP 200, estado `ready`, PostgreSQL online, storage listo, safe mode activo y live mode desactivado.
- Migraciones: **55/55**, sin faltantes, inesperadas ni duplicadas.
- `/health`: HTTP 200; cola `pending=0`, `failed=0` inmediatamente despues del despliegue.
- Logs: sin `ERROR`, `CRITICAL`, traceback, OOM ni deadlock. Ambas instancias arrancaron correctamente.
- Gmail: proveedor `gmail`, remitente `agenciabarda@gmail.com` y credenciales OAuth presentes. Se reutiliza la evidencia real de Fase 10: envio directo e inscripcion publica recibidos. No se reautorizo ni se envio otro correo.
- WhatsApp: credenciales existentes presentes, safe mode activo y sin destinatario forzado. Se reutiliza la entrega real confirmada por el propietario en Fase 10. No se envio otro mensaje.
- Suite focalizada: **19/19 PASS** (14 seguridad/entrega + 5 normalizacion telefonica).
- Registro: idempotencia, recuperacion de respuesta perdida, concurrencia y seleccion de acreditacion: **PASS**.
- Webhook sintetico en staging: challenge valido; firma invalida rechazada con 401; evento firmado aceptado con 200 y almacenado como no correlacionado. No genero mensajes ni costo de mensajeria.
- Android: contratos de pairing, dataset, heartbeat, sincronizacion, idempotencia y revocacion: **PASS**. El cambio no toca archivos Android ni sus contratos; no fue necesario recompilar APK.

## Pruebas minimas

| Prueba | Estado | Evidencia |
|---|---|---|
| P1 readiness | PASS | `/ready` 200 |
| P2 PostgreSQL/migraciones | PASS | PostgreSQL 16; 55/55 |
| P3 inscripcion sin duplicados | PASS | regresion de idempotencia |
| P4 encolamiento email | PASS | evidencia Fase 10 + configuracion preservada |
| P5 encolamiento WhatsApp | PASS | suite focalizada y evidencia Fase 10 |
| P6 procesamiento seguro | PASS | reclamo atomico, ambiguo sin reenvio |
| P7 webhook firmado | PASS SINTETICO / BLOCKED REAL | 401 invalido; 200 firmado; sin evento autentico Meta |
| P8 persistencia de estados | PASS | PostgreSQL real local + evento sintetico staging |
| P9 idempotencia | PASS | duplicados y concurrencia verificados |
| P10 Android | PASS | contratos sin cambios |
| P11 produccion intacta | PASS | deployment y health sin cambios |

## Gates C0-C10

| Gate | Estado |
|---|---|
| C0 estado inicial | PASS |
| C1 candidato desplegado | PASS |
| C2 staging saludable | PASS |
| C3 Gmail funcional | PASS |
| C4 WhatsApp funcional | PASS |
| C5 webhooks seguros | **BLOCKED** para evidencia autentica Meta; PASS sintetico |
| C6 trazabilidad persistente | PASS para codigo y persistencia; evidencia externa pendiente |
| C7 idempotencia/reintentos | PASS |
| C8 Android compatible | PASS |
| C9 produccion intacta | PASS |
| C10 costo adicional | PASS — USD 0 |

## Produccion y proveedores compartidos

Produccion `loving-nature` permanece en deployment `46f0dd49-e762-4ca9-8823-c3c65f72e812`, digest `sha256:89db889ed4f5b71371557f6b9c75f4260e6f245ebbc362032a0457632a00711c`, una instancia `RUNNING`, `/health` 200 y version declarada 1.0.0. No se modificaron variables, servicios, Meta, Google, `main`, ramas remotas ni planes.

Staging y produccion comparten las credenciales de Gmail y Meta, aunque sus bases y colas son independientes. El aislamiento operativo queda protegido por safe mode y ausencia de destinatario forzado, pero no equivale a aislamiento de proveedor.

## Unica accion humana pendiente

Para certificar C5 con evidencia autentica, el propietario debe autorizar explicitamente una ventana controlada para suscribir la App `BITORA Staging WA` a la WABA compartida, aceptando que Meta comenzara a remitir eventos del numero existente al callback de staging, o proporcionar una suscripcion aislada. No se realizo ese cambio global porque podria afectar o exponer eventos de produccion.
