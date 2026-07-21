# LOCAL MACHINE DIAGNOSTIC

Fecha: 2026-07-20

## Objetivo

Preparar esta PC para ejecutar BITORA BDF en staging.

## Windows

- Producto: Windows 10 Pro.
- Edicion: Professional.
- Version: 2009.
- Build: 26200.
- Arquitectura: 64 bits.
- Tipo de sistema: x64-based PC.
- Hypervisor presente: True.

## Virtualizacion

- Virtualizacion en firmware: habilitada.
- Procesador: AMD Ryzen 7 5700G with Radeon Graphics.
- La consulta de Windows Optional Features requiere elevacion administrativa.
- La sesion actual no tiene privilegios de administrador.

Comprobacion de admin:

```text
net session -> Error de sistema 5. Acceso denegado.
```

## WSL

Comandos ejecutados:

```powershell
wsl --status
wsl -l -v
```

Resultado:

```text
El Subsistema de Windows para Linux no esta instalado.
```

Estado:

- WSL: no instalado.
- WSL2: no disponible.
- Ubuntu: no instalada.

## Docker

Comandos ejecutados:

```powershell
docker --version
docker compose version
Get-Service -Name 'com.docker.service','docker'
Get-Command docker
```

Resultado:

- Docker CLI: no disponible.
- Docker Compose: no disponible.
- Servicio Docker: no encontrado.
- Docker Desktop: no detectado por PATH/servicio.

## Python

Python disponible para Codex:

```text
Python 3.12.13
pip 26.0.1
venv disponible
pip check: No broken requirements found.
```

Python del sistema:

```text
python: no reconocido
py: no reconocido
```

Impacto:

- Codex puede ejecutar los scripts con su runtime interno.
- Para uso manual desde PowerShell conviene instalar Python o usar la ruta completa del runtime.

## Git

```text
git version 2.54.0.windows.1
```

Repositorio:

```text
C:/Users/Noxie-PC/Documents/qr white label
```

Commit actual:

```text
024d772ef418081956686e524e82b85aa1669700
```

Rama:

```text
main
```

Estado:

- Repositorio limpio antes de crear estos reportes.
- Commit coincide con el requerido por la tarea.

## Proyecto BITORA

Archivos verificados:

- `Dockerfile.staging`: existe.
- `deployment/Dockerfile.staging`: existe.
- `docker-compose.staging.yml`: existe.
- `deployment/docker-compose.staging.yml`: existe.
- `deployment/scripts/bdf.py`: existe.
- `deployment/staging/.env.staging`: existe localmente.

## BDF Check

Comando ejecutado:

```powershell
python deployment/scripts/bdf.py check
```

Ejecutado usando el runtime Python de Codex.

Resultado:

```json
{
  "python": "3.12.13",
  "compose_file": true,
  "env_example": true,
  "env_file": true,
  "docker": false,
  "docker_compose": false,
  "safe_env": []
}
```

## Diagnostico final

La PC esta parcialmente preparada.

Bloqueo actual:

```text
Docker / Docker Compose no estan instalados o no estan disponibles.
WSL no esta instalado.
```

No es posible levantar BDF staging hasta completar instalacion manual de WSL2 y Docker Desktop.
