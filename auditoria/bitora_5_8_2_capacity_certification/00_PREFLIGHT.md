# Preflight

- Fecha: 2026-10-29, America/Buenos_Aires.
- Rama aislada: `certification/5.8.2-capacity-benchmark`.
- Commit de evidencia de partida: `8be0091874201a57b0675d5ba587aac9556652b0`.
- SHA de código probado por endurance: `f9dc15e3aa8abe12c72717342fcf260ef7b81bad`.
- `8be0091` solo añade documentación/evidencia respecto de `f9dc15e`.
- Working tree inicial: limpio.
- Docker: Engine 29.1.3 en Ubuntu WSL; Compose 2.40.3.
- Host WSL: 16 CPU visibles, 6,7 GiB RAM, 2 GiB swap, 952 GiB libres.
- PostgreSQL objetivo: 16, aislado y desechable.

No se utilizarán producción, datos reales, secretos productivos ni infraestructura externa.

## Smoke exploratorio descartado

`evidencia/capacity-smoke.json` corresponde a una ejecución exploratoria previa al
commit de corrección. Detectó correctamente `UNKNOWN_CREDENTIAL` para
inscripciones creadas después de activar el motor V5, pero no es evidencia de
capacidad: incorporaba cambios sin commit, mezclaba instancias con concurrencia y
falló anti-passback/idempotencia como consecuencia de ese defecto. Se conserva
únicamente como evidencia de diagnóstico.
