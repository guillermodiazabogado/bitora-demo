# BITORA RC1 - Checklist final

| Área | Estado | Evidencia |
|---|---|---|
| Funciones críticas | OK | Integridad y convivencia |
| QR | OK | Promedio 12,4 ms; p95 27,2 ms |
| 30 estaciones | OK | 3.000/3.000, p95 302 ms |
| Recepción | OK | Suite de integridad |
| Inscripción | OK | Operación y convivencia |
| Accesos | OK | Sin doble acceso |
| Cupos | OK | Robustez sin sobrecupos |
| Portal | OK | Integridad punta a punta |
| Landing | OK | Regresión existente preservada |
| NOC | OK | V6.6 y medición RC1 |
| Sala de Control | OK | Refresco optimizado |
| Reportes | OK | Caché e índices RC1 |
| Data Visualization | OK | V6.8 |
| Caché | OK | TTL acotada y métricas |
| Jobs/workers | OK | Sin pendientes ni fallidos |
| Backups | OK | Creación, checksum y restauración |
| Logs | OK | Sin errores silenciosos |
| Permisos | OK | Integridad y robustez |
| Seguridad básica | OK | Readiness productiva |
| PostgreSQL | Condicionado | Arquitectura OK; falta DSN real |
| Soak real 8 horas | Pendiente operativo | Script listo; corrida corta OK |

## Antes del piloto

- [ ] Configurar PostgreSQL real.
- [ ] Configurar almacenamiento persistente.
- [ ] Ejecutar migraciones.
- [ ] Ejecutar `verificar_production_postgres.py`.
- [ ] Ejecutar soak real de 8 horas.
- [ ] Crear y verificar backup previo.
- [ ] Confirmar que la instancia no se suspende.
- [ ] Revisar diagnóstico, jobs y webhooks.
- [ ] Hacer prueba física con lectores y red del lugar.
