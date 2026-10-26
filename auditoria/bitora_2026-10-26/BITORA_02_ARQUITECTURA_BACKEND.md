# BITORA — Arquitectura, backend y persistencia

## Diagnóstico

`server.py` posee aproximadamente 15.586 líneas y concentra configuración, autenticación, DDL, dispatch HTTP, negocio, workers, simulación y arranque. `backend/app.py` y `backend/worker.py` importan este monolito.

El backend contiene servicios de dominio razonablemente separados, pero varios solo son invocados por verificadores directos. En particular, V5.2–V5.6 y V5.8 no exponen rutas productivas equivalentes a sus capacidades internas. La excepción es Command Center V5, disponible como `GET /api/events/<id>/command-center-v5`.

## Hallazgos

| ID | Severidad | Hallazgo | Evidencia |
|---|---|---|---|
| ARC-01 | Alto | Monolito y dispatcher manual reducen mantenibilidad y testabilidad | `server.py:7460`, `server.py:15521` |
| ARC-02 | Alto | Servicios V5 enterprise inaccesibles por API productiva | Factories `server.py:385-414`; única ruta V5 principal `server.py:7686` |
| DB-01 | Alto | SQLite usa DDL/`ensure_*` embebidos; PostgreSQL aplica archivos SQL | `server.py:815-1656`, `backend/database.py:59-87` |
| DB-02 | Alto | Readiness no compara migraciones esperadas y aplicadas | `server.py:698-718` |
| ARC-03 | Medio/Alto | Lock global de proceso serializa mutaciones y no coordina réplicas | `server.py:115` |
| DB-03 | Medio | Traducción PostgreSQL propia basada en reglas sobre SQL SQLite | `backend/database.py:354-446` |
| ARC-04 | Medio | Dependencias con mínimos, sin pin exacto | `requirements.txt` |
| ARC-05 | Medio | Fuentes de versión contradictorias | `server.py:122`, Git y esquemas V5 |

## Migraciones

Se localizaron migraciones `001` a `046`, con números duplicados `007` y `015`. PostgreSQL registra por nombre completo, por lo que no hay colisión inmediata, pero la secuencia no ofrece una semántica de versión inequívoca.

La migración requerida de Command Center existe como `backend/migrations/043_v5_7_command_center.sql`.

## Escalabilidad

El servidor usa `ThreadingHTTPServer` con cola 512, pero el lock global reduce el paralelismo. Sesiones en memoria y procesos embebidos dificultan escalamiento horizontal. PostgreSQL dispone de pool, pero todavía requiere pruebas multiinstancia y eliminación de supuestos de proceso único.

## Dictamen

Core backend: **IMPLEMENTADA SIN VALIDACIÓN**.  
V5.1: **PARCIAL**.  
V5.2–V5.6 y V5.8: **PARCIAL**, por ausencia de contratos operativos.  
PostgreSQL y producción: **NO VERIFICABLE** sin certificación actual.
