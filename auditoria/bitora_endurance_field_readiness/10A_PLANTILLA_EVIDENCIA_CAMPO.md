# Plantilla de evidencia — protocolo de campo A–L

> Crear una copia por escenario y ejecución. No registrar secretos, tokens, cookies, DSN, QR reutilizables, IP completas ni datos personales. Sanitizar logs conservando correlación.

## Identificación

- Escenario: A / B / C / D / E / F / G / H / I / J / K / L
- ID de ejecución:
- Fecha/hora inicio y fin (UTC):
- Entorno/evento sintético:
- Responsable de prueba:
- Observador independiente:
- Commit/versión desplegada:
- Alcance lógico / físico:

## Inventario utilizado

| Función | Fabricante/modelo | SO/firmware | Identificador anonimizado | Red/segmento anonimizado | Configuración relevante |
|---|---|---|---|---|---|
| | | | | | |

## Precondiciones y seguridad

- [ ] Entorno aislado; no producción.
- [ ] Datos exclusivamente sintéticos.
- [ ] Relojes sincronizados y desvío registrado.
- [ ] Mecanismo de corte/restitución reversible aprobado.
- [ ] Canal de parada confirmado.
- [ ] Captura sanitizada preparada.
- Precondiciones faltantes:
- Riesgos y mitigaciones:

## Ejecución

| Paso | Hora UTC | Acción | Resultado observado | Correlación/evidencia | PASS/FAIL |
|---|---|---|---|---|---|
| 1 | | | | | |

## Mediciones

| Métrica | Umbral acordado | Resultado | Fuente |
|---|---|---|---|
| | | | |

## Reconciliación

- Operaciones generadas:
- Operaciones aceptadas:
- Operaciones rechazadas y motivo:
- Operaciones pendientes/conflictivas:
- Estado/ocupación/saldos iniciales:
- Estado/ocupación/saldos finales:
- ¿Se demostró idempotencia? Sí / No / No aplica
- ¿Se detectó pérdida o duplicación? Sí / No

## Artefactos adjuntos

| Archivo o referencia | SHA-256 | Contenido | Sanitización verificada por |
|---|---|---|---|
| | | | |

## Incidentes y desviaciones

- Incidentes:
- Pasos omitidos y justificación:
- Defectos asociados:
- Acciones de contención:

## Dictamen

- Estado: NOT RUN / BLOCKED / PASS / FAIL
- Criterios obligatorios cumplidos:
- Criterios incumplidos:
- Bloqueante, si corresponde:
- Conclusión:
- Firma responsable:
- Firma observador:
