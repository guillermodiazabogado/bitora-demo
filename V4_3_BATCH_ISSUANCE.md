# V4.3 Batch Issuance

El lote se procesa de forma controlada y sincronica para esta base. Usa participantes con decision efectiva `ELIGIBLE` o `MANUALLY_APPROVED`.

Estados:

- `PROCESSING`
- `COMPLETED`
- `COMPLETED_WITH_ERRORS`
- `FAILED`
- `CANCELLED`

No envia comunicaciones ni dispara efectos externos.
