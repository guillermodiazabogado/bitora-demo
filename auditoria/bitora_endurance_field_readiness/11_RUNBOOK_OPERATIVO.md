# Runbook operativo de campo BITORA

Fecha de preparación: 2026-10-28  
Versión base: 5.8.2  
SHA de referencia: `2b703a1c7ebaffa186976d274acdc309494140e5`  
Alcance: laboratorio y simulacro presencial controlado. No autoriza producción.

## 1. Propósito y límites

Este documento define la respuesta operativa para iniciar, observar, degradar de
forma segura, recuperar y cerrar un evento BITORA. Los comandos son referencias
para el staging aislado del repositorio; antes del simulacro deben reemplazarse
los nombres de responsables, URLs, interfaces y ubicaciones físicas marcadas
como `POR DEFINIR`.

Reglas invariables:

- no restaurar sobre la base activa;
- no ejecutar `docker compose down -v`, `DROP DATABASE`, limpieza de colas ni
  rotación de credenciales durante un incidente sin aprobación del Director de
  Operaciones;
- no borrar la SQLite Edge aunque la cola parezca dañada;
- no reintentar manualmente una operación con una nueva clave de idempotencia;
- registrar siempre hora, evento, puerta, dispositivo, instancia y correlation
  ID, sin copiar tokens, QR, secretos ni datos personales a los logs;
- `/health` prueba que el proceso vive; `/ready` determina si puede recibir
  tráfico. Una instancia no ready debe salir del balanceador;
- una prueba de laboratorio no certifica Wi-Fi, lectores, cámaras ni Edge
  físicos.

## 2. Roles y autoridad

| Rol | Responsabilidad | Autoridad de parada |
|---|---|---|
| Director de Operaciones | Declara apertura, degradación, recuperación y cierre | Evento completo |
| Líder técnico | Aplicación, balanceador, PostgreSQL, restore y evidencias | Plataforma |
| Coordinador de accesos | Puertas, lectores, anti-passback y contingencia manual | Una o más puertas |
| Operador Edge/red | Edge, LAN, Wi-Fi, switches, colas y sincronización | Segmento de red/Edge |
| Responsable de seguridad | Revocaciones, permisos, incidentes y custodia de datos | Credencial/dispositivo |
| Operador Command Center | Métricas, freshness, alertas y bitácora | Escala al Director |
| Custodio de backup | Backup, checksum, copia y restore aislado | Impide restore inseguro |

Los nombres, teléfonos, canal primario y reemplazos deben completarse antes del
simulacro. Si un rol no está cubierto, el simulacro es **NO-GO**.

## 3. Registro común de incidente

Abrir una entrada de bitácora antes de actuar:

```text
INCIDENTE:
Inicio UTC/local:
Evento / organización:
Puerta / zona:
Instancia / dispositivo / Edge:
Síntoma y primera evidencia:
Última operación correcta:
Correlation ID (si existe):
Responsable y acciones autorizadas:
Fin / condición de recuperación:
Artefactos preservados:
```

Evidencia mínima: salida de `/health` y `/ready`, estado de contenedores o
servicios, captura del Command Center con hora/freshness, profundidad de cola
Edge, logs del intervalo afectado y conteos antes/después. No capturar secretos.

En laboratorio aislado:

```powershell
docker compose --env-file .env.operational -f docker-compose.operational.yml ps
docker compose --env-file .env.operational -f docker-compose.operational.yml logs --since 15m --no-color
python scripts/operational_monitor.py --seconds 300 --output artifacts/operational-monitor.jsonl
```

## 4. Inicio del evento

**Responsable:** Director de Operaciones, asistido por Líder técnico y coordinadores de puerta.  
**Síntoma:** ventana de preapertura T-120 minutos o reinicio total planificado.  
**Diagnóstico:** confirmar SHA/version, horario, evento activo, base destino, red, recursos, última copia válida, responsables presentes y ausencia de un incidente abierto.

**Acción:**

1. Registrar SHA, versión, hora y configuración sin valores secretos.
2. Confirmar que el entorno no sea producción si se trata de simulacro.
3. Levantar PostgreSQL, aplicaciones y balanceador en ese orden. En laboratorio:
   `docker compose --env-file .env.operational -f docker-compose.operational.yml up -d --build`.
4. Esperar PostgreSQL healthy; comprobar cada instancia con `/health` y `/ready`; comprobar el gateway en `http://127.0.0.1:18787/health`.
5. Verificar login, sesión compartida, evento correcto y hora de todos los nodos.
6. Abrir Command Center y confirmar freshness, ocupación inicial, dispositivos, Edge y ausencia de alertas críticas no explicadas.
7. Ejecutar una credencial sintética de control ENTRY/EXIT y verificar auditoría y ocupación. No usar una credencial real.
8. Autorizar apertura solo después del checklist firmado.

**Verificación:** dependencias healthy/ready, ambas instancias disponibles, PostgreSQL responde, Command Center no está STALE, cola Edge en cero o explicada y operación sintética trazable.  
**Escalamiento:** un `/ready` no 200, migración pendiente, desfase horario, dataset inválido o alerta crítica bloquea apertura y escala al Líder técnico y Director.  
**Condición de recuperación:** checklist preapertura completo y autorización explícita del Director.

## 5. Comprobación de puertas

**Responsable:** Coordinador de accesos.  
**Síntoma:** preapertura de puerta, cambio de turno o inconsistencia de ocupación.  
**Diagnóstico:** comprobar asignación puerta-zona-evento, dirección ENTRY/EXIT, perfil del dispositivo, estado anti-passback, hora y conectividad.

**Acción:** identificar físicamente cada carril; validar una credencial sintética permitida, una revocada y un ENTRY duplicado; confirmar un único ALLOW, los rechazos esperados, auditoría y ocupación; bloquear la puerta ante mezcla de evento, zona o dirección.  
**Verificación:** lector, puerta y Command Center muestran el mismo resultado; el conteo vuelve al valor inicial tras el EXIT de control.  
**Escalamiento:** discrepancia de ocupación, aislamiento o anti-passback al Líder técnico; riesgo físico al Responsable de seguridad.  
**Condición de recuperación:** tres controles aprobados y puerta autorizada por el Coordinador.

## 6. Comprobación de lectores, teléfonos y tablets

**Responsable:** Coordinador de accesos y Operador Edge/red.  
**Síntoma:** inicio de turno, lectura lenta, batería baja o QR que no resuelve.  
**Diagnóstico:** revisar batería, hora automática, versión, cámara, foco, brillo, permisos, red, perfil, dispositivo ACTIVE y dataset vigente.

**Acción:** etiquetar y asociar dispositivo/puerta/operador; probar QR válido, alterado, revocado, de otro evento y repetido; probar online y luego offline controlado; confirmar persistencia local antes de mostrar éxito; disponer alimentación y reemplazo.  
**Verificación:** resultados esperados, secreto no visible, cola durable, reconexión sin duplicados.  
**Escalamiento:** dispositivo revocado, hora incorrecta, dataset inválido o pérdida de persistencia implica retiro inmediato.  
**Condición de recuperación:** equipo aprobado, dataset actual, energía suficiente y reemplazo disponible.

## 7. Verificación de Edge

**Responsable:** Operador Edge/red.  
**Síntoma:** preapertura, heartbeat ausente, dispositivo STALE o cola creciente.  
**Diagnóstico:** comprobar proceso, disco, SQLite/WAL, dataset/firma/checksum, hora, LAN/cloud, último heartbeat, secuencia y queue depth.

**Acción:** preservar SQLite; confirmar dataset CURRENT y firma/checksum; comprobar secuencia monotónica; reiniciar el cliente de control verificando que cola, secuencia y dataset sobrevivan; sincronizar de forma controlada observando ACK, RETRY, rechazo y backoff, sin editar claves de idempotencia.  
**Verificación:** creadas = persistidas; sincronizadas + pendientes + rechazadas = persistidas; perdidas = 0; cola converge a cero cuando cloud vuelve.  
**Escalamiento:** checksum/firma inválida, disco lleno, SQLite corrupta, secuencia regresiva o pérdida bloquea ese Edge.  
**Condición de recuperación:** dataset válido, heartbeat vigente, cola estable/decreciente y reconciliación sin pérdida.

## 8. Verificación de PostgreSQL

**Responsable:** Líder técnico.  
**Síntoma:** preapertura, `/ready` degradado, errores de conexión, latencia o reinicio.  
**Diagnóstico:** revisar `pg_isready`, health, conexiones, CPU/RAM/disco, locks, migraciones y logs sin imprimir DSN.

**Acción:** confirmar base/usuario/host mediante configuración enmascarada; ejecutar `pg_isready`; verificar migraciones, integridad y espacio; observar conexiones/locks sin cancelarlos automáticamente; retirar instancias no ready y detener carga no esencial.  
**Verificación:** PostgreSQL acepta conexión, `/ready` 200 dentro del límite, latencia vuelve al umbral y no hay migraciones pendientes.  
**Escalamiento:** corrupción, falta de espacio, pérdida de WAL, locks sostenidos o reinicios repetidos al responsable de base y Director; no improvisar restore.  
**Condición de recuperación:** integridad confirmada y dos ciclos consecutivos estables.

## 9. Inicio y vigilancia de Command Center

**Responsable:** Operador Command Center.  
**Síntoma:** inicio de turno, snapshot STALE, métrica discordante o alerta.  
**Diagnóstico:** consultar `/api/events/<id>/command-center-v5`, verificar evento, timestamp/freshness, fuente, estado observado/simulado/no disponible y conectividad.

**Acción:** registrar snapshot inicial; comprobar accesos, ocupación, puertas, dispositivos, Edge, conflictos, vouchers, leads y vehículos; nunca presentar cámaras no conectadas como reales; reconocer alertas solo con responsable/comentario; ante STALE usar fuentes locales y bitácora, sin inferir valores.  
**Verificación:** un evento sintético aparece dentro del SLO, la alerta de prueba abre/resuelve y ninguna fuente simulada figura como observada.  
**Escalamiento:** mezcla multievento u ocupación incoherente es crítica; STALE sostenido escala al Líder técnico.  
**Condición de recuperación:** freshness normal y dos snapshots consecutivos coherentes.

## 10. Corte de internet con LAN operativa

**Responsable:** Operador Edge/red; decisión de modo degradado por el Director.  
**Síntoma:** cloud no responde, LAN y Edge siguen disponibles.  
**Diagnóstico:** verificar gateway local, Edge, PostgreSQL local y WAN por separado.

**Acción:** registrar hora/última sync; declarar offline y no reiniciar dispositivos; mantener solo capacidades autorizadas; observar cola, disco y batería; suspender autoridad online; al volver internet usar el procedimiento de sincronización sin reemitir operaciones.  
**Verificación:** operación local persiste, cola crece de forma explicable, anti-passback local actúa dentro de su alcance y no hay pérdida.  
**Escalamiento:** cola próxima al límite, dataset vencido, conflicto masivo o disco bajo obliga a reducir/detener puertas.  
**Condición de recuperación:** enlace estable, cola cero, conflictos clasificados y Command Center fresco.

## 11. Corte de red local

**Responsable:** Operador Edge/red y Coordinador de accesos.  
**Síntoma:** múltiples dispositivos pierden Edge/gateway.  
**Diagnóstico:** revisar energía, switches, VLAN, DHCP, DNS y gateway; distinguir equipo de segmento.

**Acción:** detener ingreso afectado si no hay modo local seguro; no resetear infraestructura sin registrar configuración/autorización; conmutar solo a red de contingencia ensayada; validar dataset/persistencia antes de fallback local; registrar secuencias inicial/final.  
**Verificación:** direccionamiento/rutas correctas, heartbeat recuperado y operación de control trazable.  
**Escalamiento:** bucle, pérdida de configuración o energía a infraestructura; seguridad física al Director.  
**Condición de recuperación:** segmento estable durante el período acordado y sin cola perdida.

## 12. Caída de una instancia de aplicación

**Responsable:** Líder técnico.  
**Síntoma:** `/health` o `/ready` falla, reinicio, 5xx o alerta de balanceador.  
**Diagnóstico:** identificar instancia, salida, recursos y dependencia PostgreSQL; confirmar otra instancia ready.

**Acción:** retirar/confirmar retiro automático; preservar logs y evitar restart loop; validar sesión/operación por la instancia sana; corregir o reiniciar una vez; reincorporar solo con `/ready` 200 y smoke.  
**Verificación:** continuidad por instancia sana, sesiones compartidas, sin doble ejecución, recuperada recibe tráfico.  
**Escalamiento:** segunda instancia degradada o causa desconocida detiene carga no esencial y escala al Director.  
**Condición de recuperación:** ambas instancias ready y métricas estables en dos ventanas.

## 13. Caída o reinicio de PostgreSQL

**Responsable:** Líder técnico y responsable de base.  
**Síntoma:** `pg_isready` falla, `/ready` no 200, timeout DB o conexión rechazada.  
**Diagnóstico:** distinguir proceso, red, storage, credenciales, locks y recursos; revisar logs antes de reiniciar.

**Acción:** retirar aplicaciones no ready y tráfico online; mantener Edge offline autorizado; en reinicio ensayado reiniciar DB una sola vez; ante corrupción custodiar volúmenes/WAL y activar recuperación; al volver comprobar migraciones, integridad, sesiones y operación sintética.  
**Verificación:** `/ready` responde acotado, balanceador reincorpora, sesiones cumplen contrato y Edge sincroniza.  
**Escalamiento:** corrupción o RTO excedido al Director para continuidad offline, cierre o restore.  
**Condición de recuperación:** DB estable, integridad aprobada, tráfico normal y colas reconciliadas.

## 14. Acumulación de cola offline

**Responsable:** Operador Edge/red.  
**Síntoma:** queue depth crece o no baja al recuperar conectividad.  
**Diagnóstico:** separar backoff, revocación, ACK parcial, rechazo, dataset incompatible, espacio y transporte.

**Acción:** registrar profundidad/antigüedad/intentos/próximo retry; asegurar un solo sincronizador por SQLite; no editar estado/secuencia/idempotency key; corregir conectividad/autorización y dejar backoff; reducir tasa o puertas si crece más rápido que el drenaje.  
**Verificación:** profundidad decrece; cada operación ACKED, pendiente o rechazada con razón; creadas = persistidas y perdidas = 0.  
**Escalamiento:** cola estancada, SQLite corrupta o disco crítico al Líder técnico, conservando evidencia.  
**Condición de recuperación:** cola cero o remanente explicado/aceptado y conteos reconciliados.

## 15. Recuperación de sincronización Edge

**Responsable:** Operador Edge/red con supervisión técnica.  
**Síntoma:** conectividad restablecida o autorización corregida.  
**Diagnóstico:** validar dataset, reloj, identidad ACTIVE, alcance event/org, secuencia y capacidad servidor.

**Acción:** reabrir con lote pequeño; verificar orden, ACK e idempotencia; aumentar lote gradualmente; clasificar conflictos; comparar conteos Edge/cloud y ocupación.  
**Verificación:** cero pérdidas/duplicados efectivos, secuencia conservada y queue depth cero.  
**Escalamiento:** conflicto de integridad o mezcla multievento detiene sync y escala a seguridad/técnico.  
**Condición de recuperación:** reconciliación firmada y Command Center coherente.

## 16. Revocación urgente

**Responsable:** Responsable de seguridad; ejecución por administrador autorizado.  
**Síntoma:** dispositivo perdido, credencial comprometida, operador cesado o sesión sospechosa.  
**Diagnóstico:** verificar identidad, evento/org, motivo, alcance y solicitante.

**Acción:** registrar aprobación; revocar en fuente autoritativa; propagar dataset/estado; probar rechazo online/offline cuando actualice; retirar dispositivo y rotar solo secretos afectados según procedimiento.  
**Verificación:** intento rechazado, sesión invalidada en ambas instancias y auditoría con actor/motivo/hora.  
**Escalamiento:** dispositivo desconectado no recibe revocación: bloquear puerta/perfil y notificar seguridad física.  
**Condición de recuperación:** activo comprometido fuera de servicio y alcance confirmado.

## 17. Backup

**Responsable:** Custodio de backup.  
**Síntoma:** punto programado, antes de cambio crítico o cierre.  
**Diagnóstico:** confirmar origen, espacio, retención, cifrado, destino e integraciones.

**Acción:** registrar punto/hora; ejecutar `pg_dump -Fc` y backup consistente de storage según entorno; en laboratorio usar `python scripts/operational_postgres_restore.py --report artifacts/operational-postgres-restore.json`; calcular SHA-256/tamaño; custodiar manifiesto separado; probar restore periódicamente.  
**Verificación:** artefactos no vacíos, checksum reproducible, manifiesto y restore/integridad aprobados.  
**Escalamiento:** checksum distinto, vacío o destino inseguro bloquea cambio/cierre.  
**Condición de recuperación:** copia verificada y custodia registrada.

## 18. Restore aislado

**Responsable:** Custodio de backup y Líder técnico, con aprobación escrita del Director.  
**Síntoma:** simulacro o desastre declarado.  
**Diagnóstico:** verificar checksum, punto del backup e identidad de destino nuevo/desechable; nunca la base activa.

**Acción:** registrar aprobación/RPO; crear destino nuevo; ejecutar `pg_restore` y storage separado; desactivar integraciones externas/workers; comparar esquema, restricciones, conteos, sesiones y accesos; medir hasta servicio validado como RTO. La conmutación exige autorización separada.  
**Verificación:** checksum coincide, integridad/conteos coinciden, health/ready pasan y efectos externos = 0.  
**Escalamiento:** cualquier diferencia impide conmutación; preservar evidencia y volver al backup verificado.  
**Condición de recuperación:** restore íntegro aislado y decisión formal de conmutación o descarte.

## 19. Cierre del evento

**Responsable:** Director de Operaciones.  
**Síntoma:** horario de cierre y última salida operativa.  
**Diagnóstico:** confirmar puertas, última operación, colas, conflictos, ocupación, alertas y exportaciones.

**Acción:** cerrar ingresos y mantener EXIT según ventana; sincronizar todos los Edge; reconciliar ocupación/conflictos; tomar snapshot final y backup; exportar evidencia, cerrar sesiones privilegiadas y custodiar equipos; en laboratorio detener sin volúmenes con `docker compose --env-file .env.operational -f docker-compose.operational.yml down`.  
**Verificación:** cola cero o excepción aprobada, snapshot/backup con checksum, inventario y bitácora.  
**Escalamiento:** equipo perdido, cola no reconciliada u ocupación incoherente mantiene incidente abierto.  
**Condición de recuperación:** acta firmada y evidencia bajo custodia.

## 20. Exportación y custodia de evidencias

**Responsable:** Líder técnico y Responsable de seguridad.  
**Síntoma:** cierre, incidente o auditoría.  
**Diagnóstico:** inventariar evidencia, sensibilidad, retención y destinatarios.

**Acción:** exportar logs, JSONL, resultados, snapshots, manifiestos y checksums; enmascarar secretos/tokens/QR/PII; registrar SHA/hora/zona; conservar original read-only y copia de trabajo; transferir por canal autorizado, nunca dumps/SQLite por mensajería.  
**Verificación:** manifiesto completo, hashes coincidentes, acceso probado y secret scan.  
**Escalamiento:** exposición activa protocolo de seguridad y rotación afectada.  
**Condición de recuperación:** custodia y recepción confirmadas por escrito.

## 21. Criterios de detención

Detener la operación afectada ante: cruce de evento/organización; operación no persistida; corrupción; anti-passback o revocación crítica fallida; secreto expuesto; pérdida de trazabilidad/reloj; ambas instancias no ready; red no autorizada; o riesgo físico. Reabrir requiere causa, mitigación reversible, prueba, evidencia y autorización.

## 22. Pendientes antes del campo

Completar nombres/contactos, mapa IP/VLAN, inventario/seriales, puertas, perfiles offline, umbrales de cola/latencia/disco, SLO de freshness, objetivos RPO/RTO, retención, fuente de hora, UPS, red alternativa y autorización de cortes. Hasta entonces este runbook está **PREPARADO**, no validado presencialmente.
