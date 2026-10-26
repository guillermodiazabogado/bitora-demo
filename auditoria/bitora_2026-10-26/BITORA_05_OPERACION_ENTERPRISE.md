# BITORA — Operación enterprise y dispositivos

## Recorridos transversales

| Flujo | Estado | Diagnóstico |
|---|---|---|
| A — Participante | IMPLEMENTADA SIN VALIDACIÓN | Registro, credencial, QR y acreditación existen; recorrido no ejecutado |
| B — Offline | PARCIAL/BLOQUEADA | Dataset, cola, sync y conflictos existen; falta cliente Edge/Android verificable |
| C — Accesos | PARCIAL | V4 decide; V5.1 solo observa; ocupación enterprise puede divergir |
| D — Vouchers | PARCIAL | Grants, consumo e idempotencia internos; sin API/UI operativa |
| E — Expositor | PARCIAL | Licencias, consentimiento, leads y exportación internos; sin interfaz operativa |
| F — Vehículos | PARCIAL | Slots, ENTRY/EXIT y reconciliación internos; sin API/UI |
| G — Command Center | PARCIAL | Agrega fuentes reales, pero health/frescura y refresh son insuficientes |

## Edge

El backend contiene:

- Identidad y secretos de dispositivos.
- Datasets y checksum.
- Pairing, perfiles y capacidades.
- Firma/verificación en Event Edge.
- Cola persistente e idempotencia.
- Heartbeat y telemetría.
- Reconciliación de conflictos.
- Simulación de caída y doble consumo.

Esto constituye una base técnica, no una operación verificable. Los verificadores llaman servicios Python directamente; no se localizaron endpoints productivos equivalentes ni un cliente desplegable.

## Continuidad

Backups y restauración contemplan tablas enterprise, pero no se realizó restore. Tampoco se verificaron reconexión física, caída de red real, failover multiinstancia, operación LAN o coherencia posterior a múltiples dispositivos desconectados.
