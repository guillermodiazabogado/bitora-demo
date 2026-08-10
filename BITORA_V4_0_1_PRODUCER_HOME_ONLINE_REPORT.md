# BITORA V4.0.1 Producer Home Online Report

## Estado Inicial

- Rama fuente local: `develop/v4`
- SHA fuente: `824107bb9e8d617354e22e1dbd44766e53782af1`
- Rama de deployment: `deployment/v4-online`
- Render URL: `https://bitora-staging.onrender.com`
- Producción: no tocada
- Endurance: diferido
- PR #12: sin cambios
- Persistent Disk: pendiente de aprobación de hosting

## Estrategia

La rama `deployment/v4-online` conserva la configuración propia de Render, PostgreSQL y staging. Se incorporaron únicamente los archivos de Home Visual ya certificados desde `develop/v4`, evitando cambios en `render.yaml`, Docker, PostgreSQL, PR #12 o producción.

## Componentes a Validar Online

- Health.
- Readiness.
- PostgreSQL.
- Safe Mode.
- Live Mode OFF.
- Login sin usuario precargado.
- Productor online.
- Evento activo online.
- Home Visual.
- 12 tarjetas.
- Retorno al Home.
- Productor limitado.
- No Productor.
- Responsive.
- RBAC backend.

## Evidencia

La evidencia final debe completarse con `verificar_home_productor_online.py` y prueba visual en `https://bitora-staging.onrender.com/login.html`.

## Seguridad

No se deben versionar:

- passwords temporales;
- tokens;
- secretos;
- credenciales Render;
- dumps;
- logs crudos;
- URLs sensibles temporales.

## Resultado

Pendiente de ejecución online posterior al deploy.
