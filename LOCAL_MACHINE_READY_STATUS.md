# LOCAL MACHINE READY STATUS

Estado final:

```text
PENDIENTE DE INSTALACION MANUAL DE DOCKER
```

## Resumen

La PC esta parcialmente lista para ejecutar BITORA staging.

Listo:

- repositorio correcto;
- commit correcto;
- Git disponible;
- Python disponible para Codex;
- dependencias Python sin conflictos;
- BDF presente;
- Docker Compose file presente;
- `.env.staging` presente;
- safe mode configurado;
- storage y PostgreSQL preparados a nivel de archivos BDF.

Pendiente:

- WSL2;
- Ubuntu en WSL;
- Docker Desktop;
- Docker Compose;
- validacion `docker run hello-world`;
- ejecucion real de BDF build/up.

## Checklist del usuario

```text
□ Abrir PowerShell como Administrador
□ Ejecutar: wsl --install
□ Reiniciar Windows si lo solicita
□ Ejecutar: wsl --set-default-version 2
□ Verificar: wsl -l -v
□ Instalar Docker Desktop
□ Activar backend WSL2 en Docker Desktop
□ Activar integracion con Ubuntu
□ Verificar: docker --version
□ Verificar: docker compose version
□ Verificar: docker run hello-world
□ Ejecutar: python deployment/scripts/bdf.py check
```

## Criterio alcanzado

Escenario B de la tarea:

```text
No fue posible completar la preparacion porque falta instalacion manual, pero queda identificado exactamente que debe instalarse.
```

## Proximo paso

Instalar WSL2 y Docker Desktop. Luego volver a ejecutar:

```powershell
& "C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" deployment\scripts\bdf.py check
```
