# BITORA Demo Live 10 - Plan de prueba

## Objetivo

Validar el circuito operativo completo de BITORA con un evento controlado de 10 participantes antes de usar la plataforma en un piloto real.

## Alcance

- 1 evento independiente.
- 10 participantes.
- 4 roles operativos.
- 3 actividades.
- 2 espacios.
- 2 tipos de acreditacion.
- Reservas, lista de espera, QR, acceso, asistencia, comunicaciones, certificados, backup y restauracion.

## Entorno

- Local/demo automatizado para regresion tecnica.
- Staging/Render para ejecucion humana con dispositivos reales.
- Safe mode activo para comunicaciones hasta validar destinatarios autorizados.

## Responsables

- Super Admin: configuracion, permisos, diagnostico, backup/restauracion.
- Productor: agenda, participantes, reportes.
- Recepcion: busqueda, acreditacion y soporte de QR.
- Acceso: validacion de QR y asistencia.
- Comunicaciones: plantillas, audiencias, envios y seguimiento.

## Criterios de exito

- No hay mezcla entre eventos.
- QR valido entra una sola vez.
- QR duplicado o invalido se rechaza.
- Reservas no superan cupo.
- Lista de espera/promocion funciona.
- Comunicaciones respetan consentimiento.
- Backup de evento se inspecciona y restaura.
- Evento restaurado queda aislado y no reenvia comunicaciones.

## Criterios de bloqueo

- Perdida o corrupcion de datos.
- Acceso cruzado entre eventos.
- Sobrecupo confirmado.
- QR duplicado aceptado sin regla explicita.
- Restauracion parcial sin rollback.
- Permiso sensible ejecutado por rol incorrecto.

## Tabla de control

| Paso | Responsable | Resultado esperado | Resultado obtenido | Evidencia | Estado | Observaciones |
|---|---|---|---|---|---|---|
| Entorno | Super Admin | Health, DB, storage, jobs OK | Automatizado | `verificar_demo_live_10.py` | aprobado | Validacion humana pendiente en Render |
| Evento | Super Admin | Demo Live 10 creado | Automatizado | JSON resultado | aprobado | |
| Usuarios | Super Admin | Roles asignados por evento | Automatizado | Auditoria/DB temporal | aprobado | |
| Participantes | Productor | 10 perfiles controlados | Automatizado | JSON resultado | aprobado | |
| QR y acceso | Acceso | 10 OK, duplicados rechazados | Automatizado | JSON resultado | aprobado | |
| Reservas | Productor | Cupo 5 respetado | Automatizado | JSON resultado | aprobado | |
| Comunicaciones | Comunicaciones | Cola e historial creados | Automatizado | JSON resultado | aprobado con observaciones | Envio real requiere credenciales |
| Backup/restauracion | Super Admin | Nuevo evento restaurado | Automatizado | JSON resultado | aprobado | |
| Dispositivos reales | Todos | PC + celular + lector | Pendiente | Capturas/videos | pendiente | Requiere ejecucion presencial |
