# BITORA — Matriz consolidada de riesgos

| ID | Severidad | Componente | Riesgo | Dependencias | Confianza |
|---|---|---|---|---|---|
| R-01 | CRÍTICO | Accesos | Motor V5.1 no gobierna la decisión QR | Scanner, ocupación, Command Center | Alta |
| R-02 | CRÍTICO | Multievento | `/api/validate` no verifica asignación al evento del token | Auth/RBAC | Alta |
| R-03 | ALTO | APIs V5 | Módulos V5 internos sin contratos productivos | UI, clientes y operación | Alta |
| R-04 | ALTO | Offline | Sin cliente Edge/Android verificable | Dispositivos, LAN, sincronización | Alta |
| R-05 | ALTO | Seguridad web | Sin CSRF y cookie sin `Secure` | Proxy/HTTPS/frontend | Alta |
| R-06 | ALTO | Credenciales | PIN con salt global y sin rate limiting | Usuarios/observabilidad | Alta |
| R-07 | ALTO | Dispositivos | Estado `PROVISIONED` aceptado al autenticar | Pairing/activación | Alta |
| R-08 | ALTO | Secretos | Fallbacks constantes para dominios sensibles | Configuración/rotación | Alta |
| R-09 | ALTO | Persistencia | Posible deriva SQLite/PostgreSQL | Migraciones/restore | Alta |
| R-10 | ALTO | Readiness | No detecta migraciones pendientes | Deploy/upgrade | Alta |
| R-11 | ALTO | Command Center | Sin refresh y health parcialmente constante | Operación LIVE | Alta |
| R-12 | MEDIO | Escalabilidad | Sesiones y locks de proceso | Multiinstancia | Alta |
| R-13 | MEDIO | Arquitectura | Monolito de 15k líneas | Mantenibilidad y QA | Alta |
| R-14 | MEDIO | PostgreSQL | Adaptador SQL propio no recertificado | Persistencia | Media/Alta |
| R-15 | MEDIO | Supply chain | Dependencias sin pin/SBOM | Builds y CVE | Alta |
| R-16 | MEDIO | UX | Controles visibles sin función operativa | Usuarios de evento | Alta |
| R-17 | MEDIO | Trazabilidad | Versiones y documentos contradictorios | Release management | Alta |

No se identificó evidencia suficiente para rebajar estos riesgos mediante resultados actuales reproducibles.
