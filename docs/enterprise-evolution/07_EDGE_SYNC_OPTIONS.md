# BITORA V5 Discovery - Edge Sync Options

## Estado Actual

No se encontro motor formal de sync offline. Hay:

- SQLite local/demo;
- localStorage para captation/networking;
- jobs locales;
- R2/PostgreSQL online;
- QR/access server-authoritative.

No hay evidencia de CRDT, device identity completa, cola persistente por terminal o reconciliacion cloud-edge-device.

## Option A - Server-authoritative + Persistent Queues

Descripcion:

- Cloud sigue siendo autoridad.
- Edge/device guarda dataset minimo firmado/versionado.
- Operaciones offline se encolan con idempotency keys.
- Al reconectar, servidor acepta/rechaza y devuelve reconciliacion.

Ventajas:

- Menor complejidad.
- Mas facil de auditar.
- Compatible con QR/accreditations actuales.
- Buena base para eventos chicos/medianos.

Riesgos:

- Offline prolongado puede generar conflictos.
- Requiere reglas claras para revocaciones y anti-passback offline.

Recomendacion: PRIMERA OPCION.

## Option B - Event Sourcing Parcial + Reconciliation

Descripcion:

- Access events append-only son fuente de estado.
- Snapshots derivan ocupacion/current zone.
- Reconciliacion reconstruye estado.

Ventajas:

- Excelente auditoria.
- Bueno para command center.
- Maneja replays.

Riesgos:

- Mayor complejidad que A.
- Requiere disciplina fuerte de eventos.

Recomendacion: usar para Access State Engine, no para todo BITORA inicialmente.

## Option C - CRDT

Descripcion:

- Estado distribuido mergeable entre nodos.

Ventajas:

- Offline multi-master sofisticado.

Riesgos:

- Complejidad alta.
- Dificil auditar decisiones de acceso fisico.
- No parece necesario para baseline actual.

Recomendacion: DEFER. No adoptar salvo requisitos futuros de multi-edge simultaneo sin autoridad central.

## Recomendacion

Combinar:

- Option A para sync operativo.
- Event log append-only para accesos y consumos.
- Reconciliacion deterministica en servidor.

No usar CRDT en V5 inicial.
