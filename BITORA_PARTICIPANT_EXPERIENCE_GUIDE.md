# BITORA Participant Experience Guide

## Alcance V4.0.3

La experiencia del participante queda centrada en un unico evento activo y en el enlace personal del participante.

La navegacion disponible es:

- Inicio
- Mi QR
- Agenda
- Mis charlas
- Asistencia
- Certificado
- Notificaciones
- Perfil
- Ayuda

## Principios

- El participante no ve paneles administrativos.
- El token no se muestra como texto tecnico.
- El QR sigue funcionando con el enlace personal.
- Agenda y reservas usan los endpoints existentes del portal.
- Asistencia y certificado muestran solo datos relacionados con la acreditacion del participante.
- La vista mobile usa navegacion inferior con accesos directos.

## Flujo

1. El participante ingresa desde su link personal.
2. BITORA resuelve la acreditacion por token.
3. El backend devuelve solamente datos del evento y de la acreditacion correspondiente.
4. La interfaz presenta resumen, QR, agenda, charlas, asistencia, certificado, avisos y perfil.

## No incluido

- No se agregan envios reales.
- No se cambia la arquitectura de comunicaciones.
- No se habilita produccion.
- No se ejecuta Endurance.
