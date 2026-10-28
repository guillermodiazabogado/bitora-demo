# Protocolo de campo — infraestructura física y red

Estado de la línea base: **NO EJECUTADO**. Este documento define una prueba futura; no acredita que se haya probado hardware, red, cámaras, periféricos ni dispositivos físicos.

## 1. Objetivo y alcance

Validar en un entorno aislado de campo la continuidad operativa de BITORA desde el dispositivo hasta el servidor, incluyendo autenticación de dispositivos, accesos QR, operación offline, sincronización, monitoreo y recuperación. Las pruebas usan identidades y eventos sintéticos. Quedan fuera de alcance producción, datos personales reales, pruebas destructivas, restauraciones y cambios de firmware.

La ejecución debe tener un responsable de prueba y un observador independiente. Cada escenario se registra en `10A_PLANTILLA_EVIDENCIA_CAMPO.md`; sin evidencia completa, el resultado no puede ser PASS.

## 2. Estados y regla de decisión

| Estado | Significado |
|---|---|
| NOT RUN | El escenario todavía no fue ejecutado. No implica éxito ni fallo. |
| BLOCKED | Falta una precondición, componente o autorización indispensable. |
| PASS | Todos los criterios obligatorios se verificaron y la evidencia quedó preservada. |
| FAIL | Al menos un criterio obligatorio falló, se produjo pérdida/inconsistencia de datos o faltó evidencia requerida durante una ejecución iniciada. |

La matriz es binaria al cerrar una ejecución: **PASS o FAIL**. `NOT RUN` y `BLOCKED` son estados transitorios y no cuentan como aprobación. Un escenario abortado por seguridad se cierra como FAIL, consignando la causa.

## 3. Inventario: existente en software versus previsto

| Componente | Evidencia del repositorio | Estado verificable antes del campo | Requisito físico/externo pendiente |
|---|---|---|---|
| API, persistencia y sesiones de dispositivo | `server.py`, `backend/database.py`, `backend/services/edge_sync.py` | Implementación de software presente; no certificada en esta campaña de campo | Host aislado, PostgreSQL de prueba, reloj sincronizado |
| Provisionamiento, activación, revocación y rotación de credenciales | `backend/services/edge_sync.py`, `backend/services/event_edge.py` | Implementado a nivel de servicio/API | Dispositivo de prueba y custodia segura de credenciales |
| Dataset Edge, checksum, cola y sincronización | `backend/services/edge_sync.py`, `backend/services/event_edge.py`, `tools/edge_client/` | Implementación y cliente de referencia presentes; simulación no equivale a equipo real | Almacenamiento persistente real y cliente instalado en equipo autorizado |
| Heartbeat y estado de dispositivos | `backend/services/edge_sync.py`, Command Center en `server.py` | Modelo y visualización presentes | Red de campo, reloj/NTP y pérdida de enlace controlable |
| Lectura y validación QR | Rutas de acceso en `server.py`; soporte de terminal/scanner en servicios Edge | Flujo lógico presente; lector físico/modelo no certificado | Cámara o lector QR y navegador/cliente compatible |
| Anti-passback, ocupación e idempotencia | Servicios de acceso y sincronización bajo `backend/services/` | Controles de software presentes; concurrencia física no demostrada | Dos o más puestos/dispositivos y entradas/salidas controladas |
| Vouchers offline | Servicio de vouchers y capacidades de dispositivo bajo `backend/services/` | Flujo lógico presente; operación física no demostrada | Puntos de servicio y dispositivos autorizados |
| Lead Retrieval y consentimiento | Servicios/rutas de leads bajo `backend/services/` y `server.py` | Flujo lógico presente; dispositivo de stand no certificado | Dispositivo de expositor y dataset sintético |
| Logística vehicular | Servicio/rutas de vehículos bajo `backend/services/` y `server.py` | Flujo lógico presente; barrera/gate físico no integrado en evidencia | Gate, operador o emulador autorizado; vehículos sintéticos |
| Command Center | Rutas y vistas en `server.py` | Implementación presente; fuentes físicas no certificadas | Puesto operador, pantalla y fuentes de telemetría reales |
| Impresora, molinete, cámara de ocupación, NFC y RFID | Tipos enumerados en `backend/services/edge_sync.py` | **Previstos/modelados solamente** según la evidencia revisada; un enum no prueba un driver | Modelo, driver, protocolo, credenciales, instalación y prueba del fabricante |
| Router, switches, AP, VLAN, DHCP/DNS/NTP, firewall, UPS y balanceador físico | No constituyen artefactos físicos verificables del repositorio | NO VERIFICABLE en software | Inventario, topología, configuración sanitizada y responsables de infraestructura |

Antes de ejecutar, registrar fabricante, modelo, versión de SO/firmware, identificador anonimizado y función de cada equipo. No copiar claves, tokens, DSN, cookies ni QR válidos a las evidencias.

## 4. Preparación común y guardas

1. Crear un evento y participantes exclusivamente sintéticos, con identificadores marcados `FIELD-TEST`.
2. Usar una base aislada, con respaldo previo comprobado por el responsable; nunca apuntar a producción.
3. Registrar topología, IP enmascaradas, VLAN, DNS, NTP, ancho de banda nominal y responsables.
4. Sincronizar relojes y anotar desvío inicial de servidor, clientes y equipos.
5. Preparar captura de logs sanitizados y métricas; conservar correlación por `request_id`, `device_id` anonimizado y timestamp UTC.
6. Definir el mecanismo reversible para cortar red y energía. No desconectar infraestructura compartida.
7. Confirmar canal de parada y responsables. Abortar ante alcance inesperado, datos reales, impacto a terceros, temperatura/energía insegura o riesgo de corrupción.
8. Tomar una línea base de `/health` y `/ready`, disponibilidad de DB, cola local y estado de dispositivos. Una respuesta HTTP por sí sola no prueba el recorrido funcional.

## 5. Escenarios A–L

### A — Línea base de red y servicios

**Precondiciones:** servidor, DB, balanceador y al menos un cliente aislados; topología documentada.

**Ejecución:** (1) verificar DNS/NTP y conectividad desde cada segmento autorizado; (2) consultar liveness y readiness en 20 intervalos de 5 s; (3) realizar una operación sintética autenticada; (4) registrar latencia, errores y ruta observada.

**PASS:** 20/20 respuestas coherentes, readiness solo saludable con dependencias disponibles, operación confirmada una vez y relojes dentro del umbral acordado (por defecto ±2 s). **FAIL:** timeout, readiness falso positivo, operación duplicada o evidencia incompleta.

### B — Alta, activación y autenticación de dispositivo

**Precondiciones:** operador autorizado, dispositivo limpio, perfil y capacidades definidos.

**Ejecución:** provisionar; comprobar que PROVISIONED no puede operar; activar; autenticar con la credencial entregada; rotar credencial; comprobar rechazo de la anterior; revocar y comprobar rechazo inmediato.

**PASS:** solo ACTIVE opera, la credencial anterior y la revocada reciben rechazo, y cada transición queda auditada sin exponer secretos. **FAIL:** operación previa a activación, aceptación posterior a rotación/revocación o ausencia de auditoría.

### C — Acceso QR online de extremo a extremo

**Precondiciones:** lector/cámara identificado, participante sintético elegible, conexión estable.

**Ejecución:** leer QR; verificar autorización y evento; registrar ENTRY; confirmar estado INSIDE, ocupación y Command Center; registrar EXIT y confirmar OUTSIDE.

**PASS:** una lectura produce una sola transición correcta, el evento queda aislado y ocupación/auditoría coinciden. **FAIL:** aceptación cruzada, transición u ocupación incorrecta, duplicación o exposición de datos.

### D — Duplicados, anti-passback y concurrencia

**Precondiciones:** dos puestos sincronizados y una identidad sintética.

**Ejecución:** presentar el mismo QR simultáneamente; repetir ENTRY estando INSIDE; intentar EXIT desde estado inválido; repetir una solicitud con la misma clave idempotente.

**PASS:** exactamente una transición válida, rechazos determinísticos, ocupación neta correcta y un único efecto por idempotency key. **FAIL:** doble admisión, ocupación divergente o respuestas contradictorias sin conflicto trazable.

### E — Corte de red y operación offline de accesos

**Precondiciones:** dataset vigente con checksum validado, almacenamiento persistente y límite offline definido.

**Ejecución:** registrar línea base; cortar el enlace por el mecanismo aprobado; confirmar que `/ready` externo refleja degradación sin afectar liveness local; ejecutar secuencia autorizada ENTRY/EXIT y un rechazo; reiniciar el cliente una vez; verificar persistencia de cola.

**PASS:** decisiones locales respetan dataset/reglas, ninguna operación se pierde tras reinicio, cola y timestamps son íntegros y no hay tormenta de reintentos. **FAIL:** aceptación fuera de política, pérdida/corrupción, dependencia silenciosa de red o liveness incorrecto.

### F — Reconexión, sincronización y conflictos

**Precondiciones:** cola generada en E y una modificación conflictiva controlada en servidor.

**Ejecución:** restaurar enlace; observar backoff; sincronizar; repetir el lote; revisar ACK, conflictos y auditoría; comparar estados y ocupación local/central.

**PASS:** cada operación se aplica como máximo una vez, el reenvío es idempotente, los conflictos se clasifican y la convergencia queda demostrada. **FAIL:** duplicados, pérdida, bucle de reintento, conflicto oculto o divergencia final.

### G — Vouchers online/offline y doble consumo

**Precondiciones:** voucher sintético, dos puntos de servicio, permisos y política offline definida.

**Ejecución:** consumir online; intentar reutilización; con otro voucher cortar red y presentarlo simultáneamente en dos puntos; reconectar y sincronizar.

**PASS:** consumo online atómico; duplicado rechazado; el conflicto offline queda detectado, resuelto según política y auditado sin doble beneficio final. **FAIL:** doble consumo silencioso, saldo inconsistente o falta de trazabilidad.

### H — Lead Retrieval, consentimiento y aislamiento

**Precondiciones:** dos empresas sintéticas, licencias separadas y consentimiento configurable.

**Ejecución:** capturar lead consentido; rechazar/no persistir captura sin consentimiento según política; intentar lectura/exportación desde otra empresa; operar offline si está habilitado y sincronizar.

**PASS:** consentimiento verificable, aislamiento por empresa/evento, exportación limitada y cola protegida. **FAIL:** acceso cruzado, captura sin base válida, exportación excesiva o PII en logs. No usar personas reales.

### I — Logística vehicular y gate

**Precondiciones:** vehículos/slots sintéticos; operador o emulador explícitamente autorizado. Una barrera real requiere integración documentada.

**Ejecución:** asignar slot; autorizar gate; registrar entrada; repetir entrada; registrar salida; probar corte/reconexión si el perfil lo admite.

**PASS lógico:** transiciones, anti-passback, slot y auditoría son consistentes. **PASS físico** solo si el actuador real responde de modo seguro y queda evidencia del modelo/protocolo. **FAIL:** transición inválida, doble ingreso o actuación no controlada. Sin actuador, marcar la parte física BLOCKED, nunca inferirla del PASS lógico.

### J — Heartbeat, degradación y Command Center

**Precondiciones:** al menos dos dispositivos activos y umbrales documentados.

**Ejecución:** observar heartbeats; aislar un dispositivo; comprobar ONLINE→DEGRADED/OFFLINE y alerta; restaurar; rotar/revocar credencial; verificar visualización y auditoría.

**PASS:** tiempos coinciden con umbrales, no hay flapping indebido, recuperación es visible y el dispositivo revocado no vuelve a operar. **FAIL:** estado stale presentado como sano, alerta ausente o privilegios persistentes.

### K — Interoperabilidad de periféricos físicos

**Precondiciones:** para cada impresora, scanner, molinete, cámara, NFC o RFID: modelo, driver/protocolo, firmware, red, responsable y caso de uso aprobados.

**Ejecución por periférico:** instalar según procedimiento del fabricante; ejecutar operación nominal; dato inválido; desconexión; reconexión; reinicio; verificar resultado y estado en servidor. Para actuadores, incluir parada segura y prueba manual previa.

**PASS:** todos los periféricos declarados obligatorios completan nominal, error y recuperación sin pérdida ni acción insegura. **FAIL:** cualquier obligatorio falla. **Estado inicial: BLOCKED**, porque el repositorio solo demuestra tipos/modelos de software y no acredita hardware ni drivers concretos.

### L — Recuperación operativa y cierre de evento

**Precondiciones:** escenarios previos ejecutados, responsable de infraestructura, ventana autorizada y procedimientos de rollback.

**Ejecución:** simular pérdida controlada de DB/red y, si existe UPS/laboratorio seguro, pérdida de alimentación del puesto; verificar health/readiness; recuperar dependencias; drenar colas; reconciliar ocupación, vouchers, leads y vehículos; exportar auditoría; revocar credenciales temporales.

**PASS:** degradación rápida y visible, recuperación dentro del objetivo acordado, cero operaciones sin clasificar, balances reconciliados y credenciales temporales revocadas. **FAIL:** servicio marcado ready durante indisponibilidad, pérdida/duplicación, recuperación manual no documentada o estado final divergente. La prueba de UPS/energía queda BLOCKED hasta contar con equipo y autorización específicos.

## 6. Matriz de ejecución y decisión

| ID | Escenario | Componente mínimo | Evidencia obligatoria | Estado inicial | Resultado final |
|---|---|---|---|---|---|
| A | Red y servicios | Host, DB, balanceador, cliente | Topología, serie health/ready, latencias, operación correlacionada | NOT RUN | PASS / FAIL |
| B | Identidad de dispositivo | Cliente compatible | Transiciones, rechazos, auditoría sanitizada | NOT RUN | PASS / FAIL |
| C | QR online | Lector/cámara | Lectura, estado, ocupación, auditoría | NOT RUN | PASS / FAIL |
| D | Concurrencia | 2 puestos | Requests correlacionados, estado y ocupación | NOT RUN | PASS / FAIL |
| E | Accesos offline | Edge persistente | Checksum, corte, cola antes/después de reinicio | NOT RUN | PASS / FAIL |
| F | Reconciliación | Edge + servidor | Lote/ACK, repetición, conflictos, convergencia | NOT RUN | PASS / FAIL |
| G | Vouchers | 2 service points | Consumos, rechazo/conflicto, saldo final | NOT RUN | PASS / FAIL |
| H | Leads | 2 perfiles de empresa | Consentimiento, denegación cruzada, exportación | NOT RUN | PASS / FAIL |
| I | Vehículos | Operador/emulador; gate opcional | Transiciones y, si aplica, actuación física | NOT RUN; físico BLOCKED | PASS / FAIL por alcance |
| J | Heartbeat/Command Center | 2 dispositivos | Timeline de estados, alerta, revocación | NOT RUN | PASS / FAIL |
| K | Periféricos | Hardware/driver real | Ficha por equipo, nominal/error/recuperación | BLOCKED | PASS / FAIL |
| L | Recuperación/cierre | Infraestructura autorizada | Timeline, balances, colas, auditoría final | NOT RUN; energía BLOCKED | PASS / FAIL |

## 7. Cierre de campaña

Una campaña es apta para evaluación GO/NO-GO únicamente cuando A–J y L tienen resultado final, K se resolvió para todos los periféricos exigidos por el despliegue y no quedan operaciones sin reconciliar. Un PASS de simulador no reemplaza el escenario físico correspondiente. Los defectos deben enlazarse desde la plantilla sin incluir secretos ni datos personales.
