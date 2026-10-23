# BITORA V4 MVP Scope

## IN SCOPE

### Asistencia Real

Problema: hoy se necesita una fuente confiable de presencia real por actividad y evento.
Usuario: recepcion, control de acceso, coordinador y productor.
Flujo: configurar regla, registrar entrada/salida o asistencia manual, calcular porcentaje, cerrar asistencia.
Permisos: registrar, corregir, cerrar, reabrir y auditar separados.
Criterio: registros deduplicados, auditados, tenant-aware y elegibilidad reproducible.

### Certificados

Problema: emitir certificados solo si se cumplen condiciones.
Flujo: definir tipo y regla, calcular elegibilidad, aprobar, emitir, revocar o reemitir.
Criterio: certificado trazable, verificable, revocable y sin emision automatica no autorizada.

### Encuestas

Problema: capturar feedback y condicionar certificados si corresponde.
Flujo: crear encuesta, publicar, responder, cerrar, exportar metricas.
Criterio: versionado, privacidad y relacion auditable con elegibilidad.

### Disertantes

Problema: centralizar perfil, materiales y estado del disertante.
Flujo: invitar, completar datos, validar, publicar, asociar actividades.
Criterio: permisos minimos y storage aislado.

### Permisos por Zonas

Problema: controlar accesos fisicos mas alla del evento general.
Flujo: definir zona, asignar permiso, validar QR, registrar permitido/denegado.
Criterio: denegaciones explicitas, vigencia y auditoria.

### Historial y Autocompletado

Problema: reutilizar datos sin cruzar organizaciones ni duplicar personas.
Criterio: consentimiento, confirmacion y no sobrescritura silenciosa.

### Mejoras Operativas

Incluye centro operativo, incidencias, estado de salas y exportaciones finales.

## OUT OF SCOPE

Mercado Pago, CRM, streaming, API publica, agentes de IA, decisiones autonomas, reconocimiento facial, automatizaciones sin supervision y optimizacion automatica de recursos.
