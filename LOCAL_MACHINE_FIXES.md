# LOCAL MACHINE FIXES

Fecha: 2026-07-21

## Correcciones aplicadas

### 1. Deteccion de Docker Desktop en Windows

BDF ahora detecta Docker aunque no este publicado en el PATH global de PowerShell.

Ruta detectada:

```text
C:\Users\Noxie-PC\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe
```

Tambien inyecta esa carpeta en el PATH del proceso hijo para que Docker pueda encontrar sus credenciales locales.

### 2. Build context de Docker

Se agrego `.dockerignore` para evitar que Docker copie bases SQLite, backups, storage, logs, entornos virtuales y archivos temporales al construir la imagen.

Impacto:

```text
Build: PASSED
```

### 3. Compatibilidad PostgreSQL

Se corrigieron incompatibilidades detectadas al ejecutar BITORA sobre PostgreSQL:

- configuracion de `statement_timeout`;
- lock de migraciones para evitar carrera entre app y worker;
- traduccion de `PRAGMA table_info(...)`;
- consultas con `GROUP BY` estricto;
- lectura de escalares en repositorios compartidos.

### 4. Backup BDF

El backup ya no imprime el dump completo de PostgreSQL en consola.

Resultado validado:

```text
Backup generado: bitora-staging-20260721-040529.sql
Checksum SHA-256: 95dbc7c065bbb171d6deb95f8c995980f3c83f389af56b21a8175d2f84c81f1a
```

### 5. Restore BDF

La restauracion de staging ahora:

- detiene app, worker y monitor;
- limpia el esquema `public`;
- restaura el dump;
- vuelve a levantar servicios;
- registra reporte.

Resultado:

```text
Restore: PASSED
Health posterior: PASSED
```

### 6. Smoke-test idempotente

`verificar_demo_live_10.py` fue ajustado para usar SQLite temporal como corresponde a su diseno original. Esto evita que el smoke-test escriba datos repetidos en PostgreSQL staging despues de un restore.

Resultado:

```text
Smoke test: PASSED
```

## Correcciones no realizadas

No se configuraron proveedores externos live:

- Google OAuth;
- Resend/email real;
- Meta/WhatsApp Cloud API;
- webhooks publicos.

Esos puntos quedan para la siguiente fase con credenciales sandbox/live controladas.
