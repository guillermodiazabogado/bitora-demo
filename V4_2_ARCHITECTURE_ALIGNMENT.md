# V4.2 Architecture Alignment

V4.2 consume hechos de `attendance_records` de V4.1 y agrega una capa separada para reglas, cierres, evaluaciones, elegibilidad, overrides y reaperturas.

## Decisiones

- No se modifica `activity_attendance` legacy.
- No se emiten certificados ni PDFs.
- No se disparan jobs, emails, WhatsApp ni encuestas.
- Los snapshots se guardan como JSON normalizado con hash estable.
- Los cierres referencian una version publicada e inmutable de reglas.
- Los overrides no sobrescriben el resultado automatico: solo modifican el resultado efectivo.

## Ajustes Sobre Diseno Previo

El cierre por jornada queda fuera de alcance porque no existe una entidad jornada inequívoca en el modelo vigente.
