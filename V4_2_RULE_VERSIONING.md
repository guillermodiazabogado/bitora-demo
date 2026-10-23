# V4.2 Rule Versioning

Estados:

- `DRAFT`
- `PUBLISHED`
- `RETIRED`

Una version publicada queda como evidencia historica. Un cierre siempre referencia `attendance_rule_set_versions.id` con estado `PUBLISHED`.

Cambiar reglas no recalcula cierres historicos. Para reflejar correcciones o nuevas reglas se debe reabrir y crear un nuevo cierre.
