# BITORA — Seguridad y control de accesos

## Matriz de hallazgos

| ID | Componente | Descripción | Impacto | Prob. | Severidad | Recomendación | Confianza |
|---|---|---|---|---|---|---|---|
| SEC-01 | `/api/validate` | No exige permiso sobre el evento resuelto desde el QR | Ruptura de aislamiento multievento | Media | Alto/Crítico | Resolver evento y autorizar antes de decidir/escribir | Alta |
| SEC-02 | Access State V5.1 | Anti-passback se ejecuta en shadow después de la decisión V4 | Replay o transición inválida aceptada | Alta | Crítico | Convertir V5.1 en autoridad transaccional y fail-closed | Alta |
| SEC-03 | Sesión | Cookie carece de atributo `Secure` | Secuestro de sesión | Media | Alto | `Secure`, `HttpOnly`, política SameSite y prefijo `__Host-` | Alta |
| SEC-04 | CSRF | Sin token CSRF ni validación Origin/Referer para mutaciones | Operaciones inducidas desde navegador autenticado | Media | Alto | Token ligado a sesión y validación de origen | Alta |
| SEC-05 | Login/PIN | Sin rate limiting/lockout; PBKDF2 con salt global fijo | Fuerza bruta y crackeo correlacionable | Media/Alta | Alto | Argon2id/salt individual, backoff y alertas | Alta |
| SEC-06 | Device Identity | `PROVISIONED` puede autenticarse como `ACTIVE` | Bypass del gate de activación | Media | Alto | Operación solo en `ACTIVE` | Alta |
| SEC-07 | Secrets | Encuestas y speakers poseen secretos fallback constantes | Falsificación/correlación de tokens | Media | Alto | Fallar al arrancar fuera de desarrollo | Alta |
| SEC-08 | Sesiones | Estado en diccionario de proceso | Inconsistencia al reiniciar/escalar | Alta | Medio | Store compartido y revocación | Alta |
| SEC-09 | Usuarios | `/api/users` pertenece a allowlist pública | Enumeración de cuentas/roles | Media | Medio | Exigir autenticación o reducir respuesta | Alta |

## Evidencia clave

- Hash PIN: `server.py:3980-3987`.
- Cookie: `server.py:12443`.
- Auth global: `server.py:7648-7657`.
- Permisos por evento: `server.py:7495-7522`.
- Validación legacy/V5 shadow: `server.py:15396-15452`.
- Device auth: `backend/services/edge_sync.py:75-88`.

## Controles positivos

- RBAC central por evento y organización.
- Auditoría de denegaciones.
- QR y secretos generados con CSPRNG.
- Hashes y constraints de idempotencia Edge.
- Scoping organización/evento en varios servicios.
- Gate de configuración online para HTTPS, login, PostgreSQL y secretos generales.

No se ejecutaron ataques ni pruebas intrusivas.
