# BITORA - Reporte de estado operativo

Fecha: 2026-07-20
Commit actual: `024628cfe7c88ef2a258acf904fd3f91ec34dfc9`
Repositorio: `guillermodiazabogado/bitora-demo`
Estado general: **aprobado tecnicamente para demo controlada; pendiente validacion operativa humana con dispositivos reales y credenciales productivas finales**.

## Resumen ejecutivo

BITORA evoluciono desde un MVP local de acreditaciones QR hacia una plataforma multi-evento con usuarios, roles, permisos por evento, inscripcion publica, portal del participante, recepcion, acceso QR, reservas, cupos, asistencia, certificados, reportes, diagnostico, backups/restauracion, PostgreSQL preparado, email productivo preparado y WhatsApp Cloud API productivo preparado.

El sistema ya cuenta con una prueba automatizada denominada `Demo Live 10`, que valida un circuito completo con 10 participantes y deja evidencia en `output/demo_live_10/demo_live_10_result.json`.

La recomendacion actual es avanzar a una **demo controlada en Render con 10 personas autorizadas**, manteniendo safe mode para comunicaciones hasta completar credenciales reales.

## Modulos implementados

### Multi-evento y usuarios

- Super Admin con vision global.
- Eventos independientes con `event_id`.
- Roles por evento.
- Matriz editable de permisos.
- Menu filtrado por permisos.
- Aislamiento de usuarios por evento.
- Preparacion para Productor, Coordinador, Recepcion, Acceso, Visualizador, Comunicaciones y Soporte Tecnico.

### Inscripcion y portal

- Landing publica por evento.
- Formulario de inscripcion.
- Tipos de acreditacion.
- Consentimiento email/WhatsApp.
- Portal personal por token.
- QR individual.
- Agenda personal.
- Reservas y cancelaciones.
- Asistencias y certificados visibles cuando corresponde.

### Recepcion y acceso

- Busqueda operativa.
- Acreditacion manual.
- Validacion QR centralizada en backend.
- Rechazo de QR inexistente, duplicado, cancelado o fuera de regla.
- Escaner con camara, foto QR y token manual.
- Registro de accesos y auditoria.

### Agenda, actividades y cupos

- Espacios y actividades por evento.
- Control de cupos.
- Reservas por actividad.
- Lista de espera.
- Promocion por cancelacion.
- Validacion de acceso por actividad.

### Asistencia y certificados

- Asistencia separada de acreditacion.
- Registro de ingreso a actividad.
- Porcentaje de asistencia.
- Elegibilidad.
- Certificado preparado/generado segun reglas.
- Reportes de asistencia/elegibilidad.

### Comunicaciones

- Centro de Comunicaciones integrado con permisos.
- Plantillas.
- Audiencias.
- Cola de envios.
- Historial.
- Metricas.
- Consentimiento.
- Reintentos.
- Auditoria.
- Datos personales enmascarados segun permiso.

### Email productivo

- Proveedor Resend desacoplado.
- Validacion de dominio/remitente.
- Safe mode.
- Destinatario forzado para pruebas.
- Webhook verificado.
- Eventos de entrega idempotentes.
- Supresion por rebote/queja.
- Documentacion operativa.

### WhatsApp productivo

- Proveedor Meta Cloud API desacoplado.
- No usa WhatsApp Web ni librerias no oficiales.
- Validacion de configuracion.
- Plantillas aprobadas preparadas.
- Telefonos normalizados.
- Safe mode.
- Destinatario forzado para pruebas.
- Firma de webhook con `WHATSAPP_APP_SECRET`.
- Estados enviado/entregado/leido/error.
- Mensajes entrantes registrados.
- Eventos idempotentes.
- Supresion de telefonos.
- Documentacion operativa.

### Reportes, diagnostico y monitoreo

- Reportes operativos.
- Diagnostico tecnico.
- Salud de API, base, jobs, webhooks, backups, comunicaciones.
- Preparacion para NOC, simulador vivo y visualizacion avanzada.

### Backups, restauracion y storage

- Backup completo.
- Backup individual por evento.
- Storage separado por evento.
- Restore seguro de backup de evento como nuevo evento.
- Validacion de manifest/checksum.
- Regeneracion de tokens.
- Comunicaciones y jobs restaurados como inactivos.
- Aislamiento de archivos y datos.
- Correcciones realizadas por Demo Live 10:
  - No duplicar preferencias globales de comunicacion al reutilizar una persona.
  - Limpiar `idempotency_key` en colas restauradas para evitar colision.

### PostgreSQL

- SQLite se mantiene para local/demo.
- PostgreSQL preparado para produccion inicial.
- Migraciones versionadas.
- Migrador SQLite a PostgreSQL.
- Indices y tablas extendidas para email/WhatsApp.
- Prueba live PostgreSQL queda pendiente por falta de `QR_POSTGRES_DSN` real.

## Pruebas ejecutadas

- `verificar_v7_whatsapp_productivo.py`: OK.
- `verificar_demo_live_10.py`: OK.
- `verificar_v6_1_email_productivo.py`: OK.
- `verificar_comunicaciones_permisos.py`: OK.
- `verificar_event_restore.py`: OK.
- `verificar_storage_event_backup_restore.py`: OK.
- `verificar_integridad_bitora.py`: OK.
- `verificar_convivencia_modulos.py`: OK.
- `verificar_postgres.py`: OK estatico; live SKIP por no existir `QR_POSTGRES_DSN`.
- `verificar_production_postgres.py`: OK preparacion; prueba real pendiente.

## Resultado Demo Live 10 automatizada

- Participantes: 10.
- Actividades: 3.
- Reservas confirmadas: 5.
- Reservas canceladas: 1.
- Accesos concedidos: 10.
- Accesos rechazados controlados: 2.
- QR duplicado: rechazado.
- QR invalido: rechazado.
- Asistencias: 18.
- Certificados/elegibilidades: 18.
- Comunicaciones registradas: 20.
- Email en cola demo/control: 10.
- WhatsApp en cola demo/control: 10.
- Backup inspeccionado: OK.
- Evento restaurado: OK.
- Participantes restaurados: 10.
- Actividades restauradas: 3.
- Colas restauradas inactivas: 20.

## Estado operativo actual

BITORA esta listo para:

- Mostrar una demo funcional.
- Crear evento.
- Inscribir participantes.
- Operar QR.
- Probar reservas.
- Probar recepcion/acceso.
- Mostrar portal.
- Generar backup/restauracion.
- Mostrar comunicacion en modo controlado.

BITORA todavia requiere validacion real para:

- Envio real de email con dominio verificado.
- Envio real de WhatsApp con Meta Cloud API y plantilla aprobada.
- PostgreSQL real conectado.
- Operacion en Render con persistencia definitiva.
- Prueba con celulares/camaras reales.
- Medicion de latencia y tiempos de operador.

## Pendientes criticos antes de piloto real

1. Configurar PostgreSQL real en Render/Railway/VPS.
2. Configurar disco persistente o storage externo.
3. Configurar dominio/remitente Resend.
4. Configurar Meta WhatsApp:
   - Access token productivo.
   - Phone Number ID.
   - Business Account ID.
   - Verify Token.
   - App Secret.
   - Plantilla aprobada.
5. Ejecutar Demo Live 10 con personas/dispositivos reales.
6. Registrar incidentes.
7. Repetir segunda ejecucion despues de corregir bloqueos.
8. Confirmar backups/restauracion en entorno online.

## Recomendacion

Estado recomendado: **aprobado con condiciones para demo controlada**.

No declararlo aun apto para evento real masivo hasta completar infraestructura productiva, proveedores reales y prueba humana con dispositivos.
