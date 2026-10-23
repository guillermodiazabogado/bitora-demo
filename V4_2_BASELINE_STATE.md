# V4.2 Baseline State

Fecha: 2026-07-28
Rama base: develop/v4
Rama de trabajo: feature/v4.2-attendance-closure-eligibility
Commit base local: 678579c55550c94c320016520c8058e1057ccb14
Commit V4.1: 4f11dc17719dab26f2f3f346d17ca13bdc67700a
PR V4.1: https://github.com/guillermodiazabogado/bitora-demo/pull/1
Estado PR V4.1: MERGED
Commit de merge V4.1: 678579c55550c94c320016520c8058e1057ccb14

## Estado

- Working tree inicial: limpio.
- V4.1 incorporado a develop/v4.
- Feature flag V4.1: `attendance_v4_enabled`.
- Feature flag V4.2: `attendance_closure_eligibility_v4_enabled`.
- Hallazgo heredado: script historico de upgrade documentado en `INHERITED_SECURITY_FINDING_UPGRADE_SCRIPT.md`.
- Release Candidate congelada: no modificada.
- Endurance 24h: no ejecutado.

## Riesgos

V4.2 agrega migracion y endpoints nuevos. Por matriz de recertificacion requiere regresion de seguridad, aislamiento, backup/restore y V4.1.
