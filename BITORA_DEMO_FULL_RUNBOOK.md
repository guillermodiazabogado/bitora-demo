# BITORA Demo Full Runbook

## Objetivo

Guia para presentar BITORA online de punta a punta con datos ficticios y sin consola.

## URL

- Staging: `https://bitora-staging.onrender.com`
- Login: `https://bitora-staging.onrender.com/login.html`

## Demo

- Organizacion: BITORA Demo
- Evento: BITORA Demo Full 2026
- Datos: 100% ficticios
- Safe Mode: ON
- Live Mode: OFF
- Comunicaciones reales: 0

## Recorrido sugerido de 15 minutos

1. Admin
   - Ingresar al login.
   - Abrir Usuarios y Permisos.
   - Mostrar usuarios demo, roles y matriz.
   - Abrir Configurar Evento y confirmar evento activo.

2. Productor
   - Ingresar como `productor-demo-online`.
   - Ver Home Visual.
   - Abrir Inscripciones, Agenda, Speakers, Encuestas, Comunicaciones, Analytics y Operations Center.
   - Mostrar que Persistent Storage puede seguir como limitacion conocida de hosting.

3. Participante
   - Abrir el Portal URL de Juan Demo.
   - Mostrar Inicio, Mi QR, Agenda, Mis charlas, Asistencia, Certificado, Notificaciones y Perfil.
   - Reservar una actividad si se desea mostrar interaccion.

4. Recepcion
   - Ingresar como `recepcion-demo-online`.
   - Buscar `Juan Demo`.
   - Mostrar acreditacion y estado.

5. Acceso
   - Ingresar como `acceso-demo-online`.
   - Validar QR o carga manual segun capacidad disponible del navegador.
   - Mostrar bloqueo de doble validacion si aplica.

6. Cierre
   - Volver a Productor/Admin.
   - Mostrar Analytics y Operations Center con datos derivados.

## Criterios de suspension

- Error general de login.
- Perdida de aislamiento por rol.
- Envio externo inesperado.
- Datos reales visibles.
- Error persistente de PostgreSQL.
- Fallo de health check.

## Notas

No incluir passwords en este archivo. Las claves demo se entregan una sola vez al finalizar la preparacion.
