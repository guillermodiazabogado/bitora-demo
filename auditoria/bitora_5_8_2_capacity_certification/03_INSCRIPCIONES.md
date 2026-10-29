# Capacidad de inscripciones

Contrato real: `GET /api/event`, `POST /api/register` con `actor=public`, `GET /api/portal`, `GET /api/qr.svg`. Solo cuenta como completa una alta nueva HTTP 201, `existing=false`, token/portal/QR válidos y reconciliación final PostgreSQL.

Escalones previstos: 10, 25, 50, 100, 250, 500, 1.000 y 2.000 usuarios virtuales, continuando solo mientras el entorno sea seguro.

Estado: **NOT RUN**.
