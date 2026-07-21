# BITORA Supertest Framework

BSTF es el marco permanente de certificacion tecnica de BITORA. Centraliza auditorias, pruebas funcionales, seguridad, persistencia, backup/restauracion y preparacion de release.

## Comando principal

```bash
python run_bitora_supertest.py --standard
```

## Perfiles

- `--quick`: smoke test de integridad, convivencia, email, WhatsApp, backup/restore, demo live y PostgreSQL estatico.
- `--standard`: perfil recomendado antes de subir cambios. Incluye seguridad, permisos, datos basura, errores humanos y concurrencia critica.
- `--full`: reservado para ampliar cobertura sin pruebas destructivas.
- `--stress`: agrega pruebas de carga/stress cuando existen scripts disponibles.
- `--security`: perfil orientado a auditoria de seguridad.
- `--disaster`: perfil para recuperacion y escenarios de contingencia.
- `--endurance`: preparado para pruebas largas de operacion continua.
- `--release`: perfil de certificacion previa a release productivo.

## Regla de aprobacion

El resultado queda aprobado solamente si:

- no fallan pruebas requeridas;
- no hay timeouts en pruebas requeridas;
- no existen hallazgos criticos o altos;
- se generan reportes completos.

Los hallazgos medios y bajos no bloquean la aprobacion, pero quedan documentados como deuda tecnica o puntos de revision.

## Reportes generados

- `BITORA_RELEASE_CANDIDATE.md`
- `BITORA_CODE_AUDIT.md`
- `BITORA_SECURITY_REPORT.md`
- `BITORA_DATABASE_REPORT.md`
- `BITORA_ARCHITECTURE_REPORT.md`
- `BITORA_SUPERTEST_REPORT.html`
- `BITORA_SUPERTEST_RESULTS.json`
- `BITORA_SUPERTEST_SUMMARY.md`
- `BITORA_LOAD_TEST_REPORT.md`
- `BITORA_DISASTER_RECOVERY_REPORT.md`
- `BITORA_RELEASE_CERTIFICATION.md`

Tambien se guarda una copia historica en `output/supertest/<timestamp>/`.

## Uso recomendado

Antes de cada cambio importante:

```bash
python run_bitora_supertest.py --quick
```

Antes de publicar en Render:

```bash
python run_bitora_supertest.py --standard
```

Antes de un evento real:

```bash
python run_bitora_supertest.py --release
```

Las pruebas destructivas, endurance y disaster reales deben ejecutarse en un entorno aislado, nunca sobre la demo publica activa ni sobre datos operativos reales.
