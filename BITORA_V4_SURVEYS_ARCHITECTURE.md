# BITORA V4 Surveys Architecture

## Alcance

Encuestas por evento, actividad, disertante y encuesta final. Pueden ser anonimas, identificadas, obligatorias u opcionales.

## Preguntas

Opcion unica, opcion multiple, escala, texto, si/no, puntuacion y matriz.

## Versionado

Una encuesta publicada no se edita destructivamente. Cambios crean nueva version. Las respuestas se asocian a la version respondida.

## Privacidad

Encuesta anonima no debe permitir reidentificacion operativa. Encuesta identificada requiere consentimiento o base operativa clara. Exportaciones respetan permisos.

## Estados

`draft`, `published`, `closed`, `archived`.

## Relacion con Certificados

Una regla de certificado puede exigir encuesta completada. No debe exigir contenido especifico salvo aprobacion explicita y auditable.

## Criterios

- Respuesta fuera de evento: rechazada.
- Respuesta duplicada: idempotente o nueva version segun configuracion.
- Exportacion sin permiso: 403 o equivalente seguro.
