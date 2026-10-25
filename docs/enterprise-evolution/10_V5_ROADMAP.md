# BITORA V5 Discovery - Roadmap

## Orden Recomendado

### V5.0 - Enterprise Core Model

Entity, Credential, Entitlement, Rule, Zone, Door y Device como modelo aditivo en shadow mode.

### V5.1 - Access State Engine

IN/OUT, anti-passback, cooldown, current zone y revocations. Primero comparar contra motor actual, luego activar por evento.

### V5.2 - Device Identity and Sync Foundation

Device registry, dataset revision, persistent queue e idempotency. Sin hardware especifico.

### V5.3 - Delegation Portal

Companies/delegations, cupos, carga masiva, aprobaciones e invitaciones.

### V5.4 - Entitlements and Vouchers

Kits, catering, parking, beneficios. Cada consumo genera evento auditable.

### V5.5 - Lead Retrieval

Construir sobre networking + consentimiento. Licenciable por stand/empresa/usuario/dispositivo/evento.

### V5.6 - VAPP Logistics

Vehicles, drivers, gates, slots, check-in/out.

### V5.7 - Command Center V5

Telemetry operacional, access flows, occupancy, devices, queue depth, alerts.

### V5.8 - Device API Adapters

Contratos y adapters para scanners, printers, NFC/RFID, turnstiles, cameras, kiosks.

## Clasificacion Must / Should / Future

MUST:

- modelo Entity/Entitlement/Rule;
- Access State Engine;
- Device identity;
- no regression gate;
- backup/restore V5.

SHOULD:

- delegation portal;
- entitlements/vouchers;
- command center V5.

FUTURE / INTEGRATION:

- biometria;
- KYC;
- RFID UHF;
- tornos;
- cashless completo;
- reconocimiento de patentes;
- infraestructura edge redundante.

## Primer ExecPlan Recomendado

V5.0 Enterprise Core Shadow Model: agregar diseno detallado y pruebas de lectura sin afectar runtime. La implementacion queda para aprobacion explicita posterior.
