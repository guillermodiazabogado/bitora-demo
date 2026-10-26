# BITORA — Frontend, interfaz y experiencia

## Estado

El frontend administrativo es HTML/CSS/JavaScript sin framework. `frontend/` y `static/` duplican los principales archivos y actualmente permanecen convergentes, aunque esto crea riesgo de mantenimiento.

Command Center consume datos reales mediante `/api/events/${state.eventId}/command-center-v5`. No utiliza arrays mock para sus métricas principales. Las comunicaciones demo y los simuladores se muestran explícitamente como tales.

## Hallazgos

- Command Center está detrás de feature flags y permisos.
- Maneja error y estado `UNAVAILABLE`.
- Distingue ocupación proyectada, acceso y cámara.
- No posee auto-refresh para operación LIVE.
- Parte del health backend es constante: DB `OK`, storage `NOT_CHECKED`, safe mode `ON`, live mode `OFF`.
- Servicios, Empresas, Networking, Leads, Vehículos y Dispositivos redirigen a una vista genérica de reportes.
- Fit, Zoom, Layers y algunos selectores aparecen sin listeners funcionales.
- PRE/LIVE/POST se expresa principalmente como estado visual, no como recorridos operativos diferenciados.
- Android no está implementado.

## Accesibilidad

Se observaron viewport, landmarks, etiquetas ARIA, regiones live y elementos de mapa enfocables. No se ejecutaron pruebas con lector de pantalla, contraste, zoom real o recorrido completo por teclado.

## Clasificación

| Área | Estado |
|---|---|
| Administración V1–V4 | IMPLEMENTADA SIN VALIDACIÓN |
| Command Center | IMPLEMENTADA SIN VALIDACIÓN |
| Venue Map | PARCIAL |
| Vouchers/leads/vehículos/dispositivos | PARCIAL; resúmenes sin operación dedicada |
| Comunicaciones demo | SIMULADA/DEMO, correctamente identificada |
| Android | NO IMPLEMENTADA |
