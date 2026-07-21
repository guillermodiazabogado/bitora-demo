# BITORA Staging Runbook

## Antes de certificar

- Repositorio limpio.
- Commit exacto identificado.
- `.env.staging` configurado sin secretos productivos.
- PostgreSQL live disponible.
- Storage persistente disponible.
- Safe mode activado.
- Destinatarios forzados configurados.

## Secuencia recomendada

1. Levantar staging desde cero.
2. Verificar `/health`.
3. Ejecutar `python run_bitora_supertest.py --standard`.
4. Ejecutar `python run_bitora_supertest.py --release`.
5. Ejecutar `python run_bitora_supertest.py --disaster`.
6. Ejecutar `python run_bitora_supertest.py --endurance --hours 24`.
7. Si 24h aprueba, ejecutar `python run_bitora_supertest.py --endurance --hours 72`.
8. Revisar `BITORA_FINAL_RELEASE_CERTIFICATION.md`.

## Criterio de decision

Solo puede declararse `APROBADA PARA DEMO FISICA CONTROLADA` si todos los gates requeridos del perfil `release` pasan y no quedan pruebas live omitidas.

## Accion ante falla

1. Registrar hallazgo.
2. Corregir bug o infraestructura.
3. Ejecutar `--standard`.
4. Ejecutar nuevamente `--release`.
5. No certificar sobre una corrida que requirio correcciones sin repetir el ciclo completo.
