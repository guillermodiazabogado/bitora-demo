# BITORA Demo Full Runbook

Estado: DEMO FULL READY
Staging: https://bitora-staging.onrender.com
Organizacion: BITORA TEST LAB
Evento: BITORA E2E TEST - 10 PARTICIPANTES - E2E10-20260810-174702
Event ID: 7
Safe Mode: ON
Live Mode: OFF
Comunicaciones reales esperadas: 0

## Ruta de 15 minutos

### 1. Admin

- URL: https://bitora-staging.onrender.com/login.html
- Usuario: admin-demo-final
- Accion: entrar al panel, abrir Usuarios y Permisos, Evento, Configuracion, Agenda y Analytics.
- Resultado esperado: acceso completo, gestion de usuarios visible, evento 7 seleccionado.

### 2. Productor

- Usuario: productor-demo-final
- Accion: entrar al Home Visual, abrir Inscripciones, Agenda, Speakers, Encuestas, Comunicaciones, Operations Center y Analytics.
- Resultado esperado: solo tarjetas autorizadas por permisos efectivos; Live Mode apagado.

### 3. Participante

- URL ejemplo: portal de participante elegible del evento 7.
- Accion: revisar Inicio, QR, Agenda, Mis charlas, Reservas, Asistencia, Certificado, Notificaciones y Perfil.
- Resultado esperado: evento activo unico, encuesta enviada y certificado disponible para participante elegible.

### 4. Recepcion

- Usuario: recepcion-demo-final
- Accion: buscar participante del evento 7 y revisar estado de acreditacion.
- Resultado esperado: puede operar recepcion segun permisos, sin modificar datos baseline durante la demo.

### 5. Acceso

- Usuario: acceso-demo-final
- Accion: validar QR acreditado y QR no acreditado.
- Resultado esperado: QR acreditado permitido; QR no acreditado bloqueado; duplicados y cruces bloqueados.

### 6. Analytics

- Usuario: productor-demo-final o admin-demo-final
- Accion: abrir Analytics del evento 7.
- Resultado esperado:
  - Participantes: 10
  - Acreditados: 8
  - Encuestas respondidas: 7
  - Tasa encuesta: 70%
  - Elegibles: 8
  - Certificados emitidos: 8

## Criterios de suspension

Suspender la demo si aparece cualquiera de estos casos:

- Safe Mode OFF.
- Live Mode ON.
- Envio real no autorizado.
- Error de autenticacion generalizado.
- Perdida de aislamiento entre eventos u organizaciones.
- Datos baseline modificados accidentalmente.
- Certificados o encuestas inconsistentes.
