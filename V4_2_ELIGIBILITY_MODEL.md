# V4.2 Eligibility Model

Estados efectivos:

- `ELIGIBLE`
- `NOT_ELIGIBLE`
- `INSUFFICIENT_DATA`
- `MANUALLY_APPROVED`
- `MANUALLY_REJECTED`

Cada decision guarda:

- resultado automatico;
- resultado efectivo;
- razones;
- actor de decision;
- referencia a override cuando exista.

V4.3 debera consumir el resultado efectivo, no recalcular el pasado.
