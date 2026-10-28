# Preflight de certificación

- Fecha: 2026-10-27 (America/Buenos_Aires).
- Repositorio: `guillermodiazabogado/bitora-demo`.
- Rama de origen: `deployment/v4-online`.
- HEAD inicial: `da6c22b1897b1ac339ad1c186967d5a0632d4aba`.
- Versión declarada: `5.8.2-rc.1`.
- Divergencia inicial: 5 commits locales por delante de `origin/deployment/v4-online`, 0 por detrás.
- Rama remota de certificación: inexistente al iniciar.
- CI: `release/**` activa exclusivamente `BITORA CI`.
- Staging y endurance: solo `workflow_dispatch`; el push de certificación no los activa.
- Docker CLI disponible; motor inicialmente detenido y luego iniciado para validación local.
- PostgreSQL CLI no está instalado localmente; la certificación PostgreSQL se ejecuta con el servicio PostgreSQL 16 aislado de GitHub Actions.

## Preservación

Se detectaron y preservaron sin incorporar: `R2_RESTORE_ISOLATED_VALIDATION.json`, `.codex-remote-attachments/`, `docs/enterprise-evolution/` y el `run-metadata.json` histórico.

## Agentes reales

- Coordinador: integración, publicación y decisión.
- Arquitectura/backend: PostgreSQL, migraciones y restore.
- Seguridad: sesiones, CSRF, permisos y secretos.
- CI/QA: workflows, artefactos y revisión independiente.

