# BITORA V4.3 Baseline State

- Branch base: develop/v4
- Branch de trabajo: feature/v4.3-certificates-foundation
- Commit base: d8d1127c9176107104088cea5304c6db7102bfc2
- V4.2 implementado: 853a299d338ad7d9b568ff4992c0e6be83ad5da8
- PR V4.2: https://github.com/guillermodiazabogado/bitora-demo/pull/2
- Merge V4.2: d8d1127c9176107104088cea5304c6db7102bfc2
- Estado Git inicial: limpio antes de iniciar V4.3
- Release Candidate: no modificada
- Endurance 24h: no ejecutado

## Feature Flags

- `attendance_v4_enabled`: requerido para V4.1.
- `attendance_closure_eligibility_v4_enabled`: requerido para V4.2.
- `certificates_v4_enabled`: requerido para V4.3.

## Hallazgos Heredados

Durante la prueba de restore V4.3 se detectaron colisiones heredadas al restaurar un evento junto al original: claves de idempotencia de asistencia y restricciones demasiado globales para certificados. Se corrigieron en restore y modelo V4.3 sin modificar datos existentes.

## Riesgos

La UI es de QA, no un diseñador visual final. La verificacion publica expone solo datos minimos y no reemplaza politicas legales de privacidad.
