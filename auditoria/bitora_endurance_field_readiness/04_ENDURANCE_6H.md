# Endurance 6 horas

Estado: **BLOCKED — NOT RUN**.

Los pre-gates de 15 y 60 minutos aprobaron. El runner y los checkpoints están preparados en `scripts/operational_integrated_endurance.py --stage 6h`.

El repositorio no tiene runners self-hosted registrados (`total_count=0`) y Docker Desktop local no responde. Un runner GitHub-hosted tiene un límite máximo de seis horas por job; una endurance de seis horas más checkout, instalación, restore, build, escaneo y carga/descarga de evidencia excedería inevitablemente ese límite. Ejecutarla allí produciría un timeout esperado, no evidencia válida.

Recurso requerido: host Linux aislado y persistente con Docker, capacidad equivalente o superior al laboratorio, al menos 7 horas de ventana, límites de CPU/RAM/disco, acceso al repositorio y procedimiento de parada. Comando preparado:

`python scripts/operational_integrated_endurance.py --stage 6h --checkpoint artifacts/field-endurance-checkpoint.json --report artifacts/multiinstance-endurance.json`

No se declara PASS ni se acorta la duración. Referencia del límite: [GitHub Actions limits](https://docs.github.com/en/actions/reference/limits).
