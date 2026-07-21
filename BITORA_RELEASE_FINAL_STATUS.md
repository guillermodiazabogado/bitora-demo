# BITORA Release Final Status

Fecha: 2026-07-21

Decision:

```text
RELEASE CERTIFICADA CON RESTRICCIONES
```

## Alcance de esta decision

La certificacion con restricciones aplica al staging local BDF.

Queda certificado localmente:

```text
Docker
Docker Compose
BDF check
Build
PostgreSQL
Aplicacion BITORA
Worker separado
Monitor
Storage persistente
Safe mode
Migraciones
Health checks
Backup
Restore
Smoke test
Email live por organizacion
```

## Restricciones

No se certifica aun como release final para piloto/evento real porque faltan validaciones externas:

```text
Google OAuth live
WhatsApp live por organizacion
Webhooks tenant-aware live
Disaster recovery live extendido
Endurance 24 horas
Upgrade desde version anterior
```

Detalle Google OAuth:

```text
GOOGLE OAUTH LIVE NO CERTIFICADO
Bloqueo actual: faltan credenciales Google Cloud y falta endpoint real de inicio/callback OAuth dentro de BITORA.
```

## Estado operativo

```text
STAGING LOCAL OPERATIVO CON RESTRICCIONES
```

URL local:

```text
http://localhost:8788
```

## Proximo paso obligatorio

Configurar credenciales sandbox/live controladas y ejecutar:

```powershell
python deployment/scripts/bdf.py supertest --profile release
```

No se debe declarar BITORA apta para evento real hasta completar los gates live externos, disaster recovery y endurance.
