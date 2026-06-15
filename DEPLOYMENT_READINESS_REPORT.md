# DEPLOYMENT READINESS REPORT - BITORA V4.6

Fecha: 2026-06-15

## Estado actual

BITORA queda preparada para una primera demo online sin ejecutar despliegue externo. El sistema mantiene compatibilidad local, red local y modo demo con SQLite.

## Dependencias

- Python 3.11 o superior recomendado.
- Pillow para generacion de credenciales/certificados.
- SQLite como base demo/local.
- PostgreSQL queda previsto por variables, pero no migrado en esta fase.

## Configuracion validada

- `APP_ENV`
- `BASE_URL`
- `PORT`
- `QR_HOST`
- `QR_DB_ENGINE`
- `QR_SQLITE_PATH`
- `QR_POSTGRES_DSN`
- `HTTPS_REQUIRED`
- `QR_REQUIRE_LOGIN`
- `QR_AUTO_BACKUP_MINUTES`
- `QR_BACKUP_KEEP_LAST`

## URLs publicas

Las URLs criticas se preparan desde `BASE_URL` cuando esta definido:

- portal participante
- QR
- landing publica
- reservas
- pantalla publica
- endpoints operativos

Si `BASE_URL` no esta configurado, el sistema conserva compatibilidad local usando URLs relativas o detectadas.

## Health check

Endpoint disponible:

```http
GET /health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "env": "demo",
  "version": "4.6-deploy-ready"
}
```

## Logs

El servidor informa al iniciar:

- version
- entorno
- base URL
- base de datos
- modo de acceso
- backups

Los errores criticos se registran por consola o archivos locales segun el entorno de ejecucion.

## Seguridad basica

Incluido:

- cabecera `X-Content-Type-Options`
- cabecera `X-Frame-Options`
- cabecera `Referrer-Policy`
- HSTS cuando corresponde HTTPS
- secretos fuera del codigo mediante variables
- `.gitignore` para no subir `.env`, bases locales, backups ni logs

Pendiente para produccion:

- usuarios y claves definitivas
- rotacion de secretos
- rate limit externo
- PostgreSQL
- backups fuera del servidor
- monitoreo externo

## Riesgos

1. SQLite no es recomendable para un evento real en cloud gratuito si el disco no es persistente.
2. Los backups actuales son locales al servidor.
3. WhatsApp, email y pagos siguen preparados pero sin integracion real.
4. El sistema esta listo para demo online, no para produccion critica masiva.
5. La concurrencia real depende del proveedor, memoria, CPU y disco.

## Mejoras realizadas en V4.6

- Version interna actualizada a V4.6.
- Archivo `.env.example` generado.
- Archivo `.gitignore` generado.
- Guia `README_DEPLOY.md` creada.
- Reporte de readiness creado.
- Prueba automatica `verificar_v4_6_deploy.py` agregada.

## Pendientes recomendados antes de produccion

1. Migrar a PostgreSQL.
2. Configurar dominio propio y HTTPS definitivo.
3. Definir usuarios, roles y claves reales.
4. Usar almacenamiento persistente para archivos y backups.
5. Agregar monitoreo externo.
6. Probar carga con el proveedor cloud elegido.
7. Integrar email/WhatsApp transaccional si el evento lo requiere.
