# BITORA Multievent Isolation Report

Fecha: 2026-07-28

## Resultado

```text
20-Event Isolation: PASSED
multievent_isolation_20_events: PASSED
```

## Falla Original

La prueba no era idempotente en PostgreSQL. Intentaba crear usuarios con nombres fijos:

```text
Usuario QA 0
Usuario QA 1
...
```

Al reejecutarse sobre staging persistente, PostgreSQL rechazaba la insercion por:

```text
users_name_key
```

## Correccion Aplicada

Se actualizo la prueba para:

```text
1. Usar un run_id unico por corrida.
2. Crear usuarios con nombres unicos.
3. Crear 20 eventos.
4. Distribuirlos entre 4 organizaciones.
5. Crear 1000 participantes.
6. Crear actividades, reservas, storage por evento, integraciones, jobs, colas y auditoria.
7. Verificar accesos cruzados por evento.
8. Verificar integraciones y jobs por organizacion/evento.
9. Verificar QR aislado por evento.
10. Verificar bloqueo de path traversal en storage.
```

## Evidencia

```text
python verificar_multievent_isolation_20_events.py
OK: aislamiento multievento 20 eventos / 1000 participantes
```

BSTF Release:

```text
multievent_isolation_20_events: PASSED
```

## Resultado De Aislamiento

```text
Eventos creados: 20
Organizaciones creadas: 4
Participantes sinteticos: 1000
Colas creadas: 20
Jobs creados: 20
Cruces entre eventos: 0
Cruces entre organizaciones: 0
Integraciones cruzadas: 0
Jobs cruzados: 0
Storage cruzado: 0
Secretos expuestos: 0
```
