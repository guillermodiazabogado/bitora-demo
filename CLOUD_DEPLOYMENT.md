# BITORA V4.5 - Cloud Demo

Objetivo: publicar una demo online gratuita para compartir enlaces, probar inscripciones reales y validar la experiencia fuera de la red local.

Esta configuracion no es produccion definitiva. Mantiene SQLite y un solo servidor.

## Variables

Minimas para demo:

```env
APP_ENV=demo
BASE_URL=https://bitora-demo.onrender.com
HTTPS_REQUIRED=true
PORT=10000
QR_DB_ENGINE=sqlite
QR_SQLITE_PATH=acreditaciones.sqlite3
QR_AUTO_BACKUP_MINUTES=10
QR_BACKUP_KEEP_LAST=24
```

Locales recomendadas:

```env
APP_ENV=development
PORT=8787
QR_DB_ENGINE=sqlite
QR_SQLITE_PATH=acreditaciones.sqlite3
```

## Render

1. Subir el proyecto a un repositorio.
2. Crear un Web Service en Render.
3. Usar:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python backend/app.py`
   - Health check path: `/health`
4. Configurar variables:
   - `APP_ENV=demo`
   - `BASE_URL=https://TU-SERVICIO.onrender.com`
   - `HTTPS_REQUIRED=true`
   - `QR_DB_ENGINE=sqlite`
   - `QR_SQLITE_PATH=acreditaciones.sqlite3`

Render define `PORT` automaticamente. BITORA lo toma sin hardcodear.

## Vercel

Opcion futura si se separa frontend/backend:

- Frontend en Vercel.
- Backend en Render.
- Configurar el frontend para consumir `BASE_URL` del backend.

Actualmente BITORA sirve frontend y backend desde el mismo proceso Python, por eso Render es el camino mas directo.

## Cloudflare Pages

Opcion futura para frontend estatico:

- Publicar `frontend/`.
- Mantener API en Render.
- Configurar reglas para apuntar `/api/*` al backend.

No usar esta opcion hasta separar formalmente frontend/backend.

## Health Check

Endpoint:

```http
GET /health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "env": "demo",
  "version": "4.5-cloud-demo"
}
```

## Demo Publica

Ejemplos:

- `https://demo.bitora.ar`
- `https://bitora-demo.onrender.com`

Con `APP_ENV=demo` se muestra la marca visual `BITORA DEMO` en login, dashboard, landing y portal participante.

## Limitaciones

- SQLite funciona para demo, pero no es alta disponibilidad.
- Los archivos de backup dependen del disco del servicio gratuito.
- WhatsApp, email y Mercado Pago siguen en modo preparado/demo.
- Para produccion real se recomienda PostgreSQL, almacenamiento persistente y dominio propio.
