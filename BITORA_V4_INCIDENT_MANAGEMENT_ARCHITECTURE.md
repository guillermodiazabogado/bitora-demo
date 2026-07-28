# BITORA V4 Incident Management Architecture

## Tipos

Acceso, acreditacion, reserva, capacidad, seguridad, tecnica, participante, disertante, comunicacion e integracion.

## Estados

`open`, `assigned`, `in_progress`, `resolved`, `dismissed`, `escalated`.

## Campos Conceptuales

Organizacion, evento, actividad opcional, participante opcional, prioridad, responsable, evidencia, comentarios, estado, timestamps y cierre.

## Reglas

Toda incidencia pertenece a un evento o a una organizacion. Comentarios son append-only. Cierre requiere resolucion o descarte con motivo.

## Notificaciones

Solo supervisadas y sujetas a Safe Mode. No escalar fuera de la organizacion sin permiso.

## Criterios

- Incidencia sin ownership: invalida.
- Cambio de estado sin auditoria: invalido.
- Visualizador no modifica.
