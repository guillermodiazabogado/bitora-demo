# Escalabilidad horizontal

| Instancias | Pool máximo agregado | Estado |
|---:|---:|---|
| 1 | 10 | NOT RUN |
| 2 | 20 | NOT RUN |
| 4 | 40 | NOT RUN |

No se supondrá escalado lineal. `/api/register` y `/api/validate` usan un `DB_LOCK` por proceso; PostgreSQL aplica además advisory lock por acreditación para proteger anti-passback.
