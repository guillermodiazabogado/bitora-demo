# BITORA 5.8.2-rc.1

Release candidate local para evaluación enterprise. No constituye autorización de producción.

## Cambios principales

- Sesiones persistentes con tokens y CSRF hasheados, expiración y revocación.
- Aislamiento de Lead Retrieval por organización, evento, compañía y usuario.
- Validación de consentimiento por compañía también en la capa de servicio.
- Cliente Edge de referencia con cola durable, reinicio, backoff y reconciliación.
- Interfaces productivas de Vouchers, Leads y Vehículos conectadas a APIs reales.
- Command Center con refresco resiliente, estado stale y salud no observada explícita.
- Contenedores reproducibles con `requirements.lock`, UID no privilegiado y readiness.
- Restore PostgreSQL limitado a bases aisladas, con checksum y confirmación tipada.
- CI ampliado para `main`, `release/**` y nuevos gates enterprise.

## Compatibilidad y migraciones

- Nueva migración: `049_persistent_auth_sessions.sql`.
- PostgreSQL objetivo: 16.
- Python mínimo: 3.12.
- Las APIs existentes se preservan; la autorización de leads se hace más restrictiva por compañía.

## Limitaciones conocidas

- La migración 049, el Docker build y el E2E completo de esta RC requieren ejecución en CI/staging autorizado.
- El cliente Edge incluido es una referencia simulable, no un dispositivo o aplicación Android certificados.
- No se certificaron cámaras, red física, proveedores externos ni hardware.
- No se ejecutó restore contra una instancia real; solo se endureció y verificó el procedimiento.

## Rollback

1. Detener ingreso de tráfico y jobs.
2. Conservar backup y checksum previos al upgrade.
3. Revertir a la imagen y commit anterior certificados.
4. No eliminar `auth_sessions`; la tabla nueva es aditiva y puede permanecer sin uso.
5. Verificar `/ready`, login, acceso, ocupación y auditoría antes de reabrir tráfico.

