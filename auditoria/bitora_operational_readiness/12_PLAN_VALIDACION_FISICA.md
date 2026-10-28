# Plan de validación física

| Componente | Recurso necesario | Responsable | Procedimiento | Resultado esperado | Evidencia | Estado | Dependencias |
|---|---|---|---|---|---|---|---|
| Lectores QR | Lectores definitivos y credenciales de prueba | Operaciones | ENTRY/EXIT, repetición y QR inválido | Lectura consistente y anti-passback | Logs, video, IDs | NOT RUN | Evento configurado |
| Teléfonos/tablets | Matriz Android/iOS | QA móvil | Flujos online/offline y rotación | UI usable y cola preservada | Capturas y logs | NOT RUN | Builds instalables |
| Edge real | Hardware Edge objetivo | Infraestructura | Pairing, dataset, corte y sync | Recuperación sin pérdida | Logs/checksums | NOT RUN | Red de prueba |
| Wi-Fi predio | APs y plano de cobertura | Redes | Recorrido y carga concurrente | Cobertura/latencia aceptadas | Heatmap y métricas | NOT RUN | Acceso al predio |
| Red cableada | Switches/cableado finales | Redes | Failover, pérdida y recuperación | Conectividad estable | Capturas y logs | NOT RUN | Acceso al predio |
| Router/switches | Configuración final | Redes | Reinicio controlado y QoS | Recuperación documentada | Config exportada | NOT RUN | Ventana de prueba |
| Corte Internet | Enlace de staging | Operaciones/Redes | Desconectar, operar, reconectar | Cola íntegra y sync idempotente | Reporte reconciliación | NOT RUN | Edge real |
| Servidor local | Host final | Infraestructura | Arranque, carga, reinicio | Health y continuidad | Logs/recursos | NOT RUN | Hardware disponible |
| Sync remoto | Servidor staging autorizado | Infraestructura | Acumular y sincronizar | Sin pérdida ni duplicados | IDs y conteos | NOT RUN | Staging externo |
| Cámaras | Cámaras/protocolo | Proveedor | Ingesta y pérdida de señal | Estado real, sin datos inventados | Video/logs | NOT RUN | Adaptador acordado |
| Conteo personas | Sensor/ API | Proveedor | Comparar conteo manual/sensor | Error dentro del umbral acordado | Dataset comparativo | NOT RUN | Decisión de producto |
| Email | Cuenta sandbox | Comunicaciones | Envío controlado y webhook | Entrega/trazabilidad | IDs sandbox | NOT RUN | Credenciales sandbox |
| WhatsApp | Número sandbox | Comunicaciones | Plantilla de prueba/webhook | Entrega/trazabilidad | IDs sandbox | NOT RUN | Credenciales sandbox |
| Proveedores | Sandboxes contractuales | Integraciones | Timeout/error/reintento | Degradación controlada | Logs correlacionados | NOT RUN | Accesos externos |
| Acreditación | Personal designado | Responsable evento | Inscripción a credencial | Flujo y tiempos aceptados | Acta y tiempos | NOT RUN | Capacitación |
| Seguridad | Personal de puertas | Responsable seguridad | ENTRY/EXIT y contingencias | Procedimiento ejecutable | Acta/video | NOT RUN | Simulacro presencial |
| Responsables | RACI firmado | Propietario | Escalamiento y recuperación | Roles y contactos confirmados | RACI/acta | NOT RUN | Decisión organizacional |
