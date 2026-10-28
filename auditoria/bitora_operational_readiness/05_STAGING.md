# Staging

Configuración: **PASS estático**. Runtime: **BLOCKED**.

`docker-compose.operational.yml` define PostgreSQL 16, dos instancias, Nginx `least_conn`, healthchecks, secretos obligatorios externos, safe mode, live mode OFF y comunicaciones desactivadas. El único puerto publicado se limita a `127.0.0.1:18787`.

`python verificar_operational_staging.py` pasó. No se desplegó staging externo ni se generaron costos. El daemon local impidió `compose up`.

