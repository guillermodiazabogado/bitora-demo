# BITORA - guia de despliegue online

Esta guia deja el proyecto listo para publicar una demo en Internet. No reemplaza la puesta en produccion final: para produccion real se recomienda migrar a PostgreSQL, configurar dominio, HTTPS, backups externos y secretos definitivos.

## 1. Preparar GitHub

1. Revisar que no se suba la base local ni secretos:
   - `.env`
   - `*.sqlite3`
   - `backups/`
   - `*.log`
2. Subir el proyecto a un repositorio GitHub.
3. Confirmar que existan:
   - `requirements.txt`
   - `Procfile`
   - `render.yaml`
   - `.env.example`
   - `README_DEPLOY.md`

## 2. Variables recomendadas

Para demo online:

```env
APP_ENV=demo
BASE_URL=https://TU-SERVICIO.onrender.com
HTTPS_REQUIRED=true
QR_DB_ENGINE=sqlite
QR_SQLITE_PATH=acreditaciones.sqlite3
QR_POSTGRES_DSN=
QR_REQUIRE_LOGIN=1
QR_AUTO_BACKUP_MINUTES=10
QR_BACKUP_KEEP_LAST=24
```

`PORT` no debe fijarse manualmente en Render/Railway si la plataforma lo asigna. BITORA lo lee automaticamente.

## 3. Render

1. Crear un nuevo Web Service.
2. Conectar el repositorio GitHub.
3. Usar:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python backend/app.py`
   - Health Check Path: `/health`
4. Configurar las variables del punto anterior.
5. Desplegar.
6. Cuando Render entregue la URL publica, copiarla en `BASE_URL`.

## 4. Railway

1. Crear proyecto desde GitHub.
2. Configurar Start Command: `python backend/app.py`.
3. Cargar las variables de entorno.
4. Usar la URL publica generada como `BASE_URL`.

## 5. VPS Linux

1. Instalar Python 3.11 o superior.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Configurar variables de entorno.
4. Ejecutar con `python backend/app.py`.
5. Para produccion usar un proxy HTTPS como Nginx/Caddy y definir `BASE_URL` con el dominio final.

## 6. Verificacion posterior

Probar:

1. `GET /health`
2. Login: `/login.html`
3. Landing publica: `/e.html?event_id=ID`
4. Inscripcion publica.
5. Portal participante.
6. Descarga/impresion de QR.
7. Escaneo QR.
8. Dashboard operativo.
9. Backup desde panel.

## 7. Limitaciones de SQLite en cloud gratis

SQLite sirve para demo. En planes gratuitos puede perder datos si el disco es efimero o si la app se recrea. Para eventos reales usar PostgreSQL, backups externos y almacenamiento persistente.
