# BITORA V4.10 Event Comparison

La comparacion entre eventos permite comparar eventos dentro de la misma organizacion.

Endpoint:

- `POST /api/analytics-v4/compare-events`

Controles:

- rechaza eventos de otra organizacion;
- exige al menos dos eventos;
- limita cantidad maxima;
- advierte si los eventos tienen configuraciones incompatibles.

Resultado esperado:

- cruces cross-tenant: 0.
