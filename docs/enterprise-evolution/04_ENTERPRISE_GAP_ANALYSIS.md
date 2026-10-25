# BITORA V5 Discovery - Enterprise Gap Analysis

| Capability | Current | Classification | Gap | Risk | Dependency | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| participant identity | acreditations/person exists | EXTEND | identidad esta centrada en person/accreditation | email unico global | people/accreditations | introducir Entity sin romper person |
| credential/QR | QR token exists | EXTEND | no hay QR dinamico/revocacion avanzada | tokens existentes | accreditations.token | mantener token actual y agregar estado versionado |
| NFC/RFID | no driver | INTEGRATION | sin Device API | acoplar hardware | Device API | dejar adapters futuros |
| documents/photo/KYC/biometric | not found | DEFER | sin modelo ni compliance | alto legal/privacidad | Identity | no implementar en V5 inicial |
| blacklist/revocation | partial status/cancel | EXTEND | no lista central de revocaciones | acceso indebido | access validation | agregar revocation layer |
| doors/zones | zones foundation exists | EXTEND | no NxN completo de puerta/zona/franja | complejidad permisos | zone tables/access | V5.0/V5.1 |
| anti-passback/cooldown | partial reentry/cooldown | EXTEND | no estado IN/OUT/current zone | datos falsos de ocupacion | access_events | Access State Engine |
| capacity hooks | capacity bags/reservations | EXTEND | no bloqueo fisico por zona | sobreaforo | zones/access | integrar estado de acceso |
| offline validation | not found | NEW | no cola persistente ni sync | evento sin internet | Device/Sync | server-authoritative + queue |
| delegation portal | not found | NEW | empresas/sponsors cargan via admin | carga manual | Entity/Company | V5.3 |
| entitlements/vouchers | not found | NEW | no derecho consumible generico | duplicar logica | Entity/Rule | V5.0 model, V5.4 UI |
| lead retrieval | networking partial | EXTEND | no licencia por stand ni scan consentido | privacidad | networking/consent | construir sobre networking |
| VAPP/logistics | not found | NEW | no vehicles/gates/slots | scope grande | Entity/Vehicle/Gate | V5.6 |
| command center | operations partial | EXTEND | tablero no consolidado real-time | falsa operacion | diagnostics/jobs/access | V5.7 |
| Device API | not found | NEW | hardware no abstraido | vendor lock-in | device identity | contrato primero, drivers despues |
| cashless | not found | DEFER | requiere ledger financiero | alto riesgo | Entitlements | solo preparar modelo |

## Biggest Gaps

1. No existe motor generico Entity/Entitlement/Rule.
2. No existe Access State Engine con IN/OUT/current zone.
3. No existe sync offline cloud-edge-device.
4. No existe Device API ni identidad de dispositivo robusta.
5. Operations Center todavia no opera como command center.
6. Comunicaciones reales dependen de configuracion externa incompleta.
7. Auditoria no parece append-only ni universal.
8. Convivencia communications legacy/V4 puede duplicar conceptos.
9. No hay modelo de delegaciones/cupos por empresa.
10. Observabilidad aun depende de diagnosticos y artefactos, no de telemetry continua.
