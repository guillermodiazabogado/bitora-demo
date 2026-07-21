# LOCAL MACHINE FIXES

## Correcciones automaticas realizadas

### 1. `.env.staging`

Se verifico que existe:

```text
deployment/staging/.env.staging
```

Estado:

- Existe.
- No esta versionado por Git.
- Esta protegido por `.gitignore`.
- BDF lo acepta como `safe_env`.

### 2. Dependencias Python

Se ejecuto:

```powershell
python -m pip check
```

Resultado:

```text
No broken requirements found.
```

### 3. BDF

Se ejecuto:

```powershell
python deployment/scripts/bdf.py check
```

Resultado:

- configuracion BDF presente;
- `.env.staging` presente;
- safe mode configurado;
- Docker faltante.

### 4. Manejo de error Docker

BDF ya informa correctamente cuando Docker no esta disponible:

```text
BDF ERROR: Docker no esta instalado o no esta disponible en PATH.
```

## Correcciones no ejecutables sin administrador

La sesion actual no tiene privilegios de administrador:

```text
net session -> Acceso denegado
```

Por lo tanto no se ejecutaron automaticamente:

- instalacion de WSL;
- activacion de Virtual Machine Platform;
- instalacion de Ubuntu;
- instalacion de Docker Desktop.

## Comandos exactos para ejecutar manualmente

Abrir PowerShell como Administrador y ejecutar:

```powershell
wsl --install
```

Reiniciar Windows si el instalador lo solicita.

Despues del reinicio:

```powershell
wsl --set-default-version 2
wsl -l -v
```

Si Ubuntu no queda instalada:

```powershell
wsl --install -d Ubuntu
```

Luego instalar Docker Desktop manualmente desde el sitio oficial de Docker.

Configuracion requerida en Docker Desktop:

- usar backend WSL2;
- habilitar integracion con Ubuntu;
- iniciar Docker Desktop;
- esperar a que quede en estado running.

Validar:

```powershell
docker --version
docker compose version
docker run hello-world
```

## Comandos BDF posteriores

Cuando Docker funcione:

```powershell
cd "C:\Users\Noxie-PC\Documents\qr white label"
& "C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" deployment\scripts\bdf.py check
& "C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" deployment\scripts\bdf.py build
& "C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" deployment\scripts\bdf.py up
& "C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" deployment\scripts\bdf.py status
& "C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" deployment\scripts\bdf.py health
& "C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" deployment\scripts\bdf.py migrate
& "C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" deployment\scripts\bdf.py smoke-test
```
