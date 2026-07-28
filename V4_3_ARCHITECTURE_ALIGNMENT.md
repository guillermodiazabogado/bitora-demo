# BITORA V4.3 Architecture Alignment

V4.3 implementa certificados como dominio separado de asistencia. Consume decisiones efectivas de V4.2 (`attendance_eligibility_decisions`) y no recalcula asistencia ni modifica cierres historicos.

## Decisiones Confirmadas

- Plantillas publicadas inmutables mediante `certificate_template_versions`.
- Emision siempre referencia tipo, version de plantilla, participante y, si aplica, decision V4.2.
- PDF generado localmente con renderer controlado y sin recursos externos.
- Documento almacenado en `storage/events/{event_id}/certificates`.
- Verificacion publica mediante token opaco hasheado.
- Revocacion y reemision son historicas; no borran ni sobrescriben documentos.

## Limites del Sprint

No se agregan emails, WhatsApp, campanas, firma digital remota, blockchain, encuestas ni automatizaciones externas.
