# BITORA User Management Online Test Plan

Runbook para validar en `https://bitora-staging.onrender.com`.

## Contexto

- Fuente: `develop/v4`
- Deployment branch: `deployment/v4-online`
- Safe Mode requerido: ON
- Live Mode requerido: OFF
- Endurance: no ejecutar
- Persistent Disk: no tocar

## Must Pass

1. Login Admin autorizado.
2. Abrir Gestion de Usuarios.
3. Crear `productor-demo-online`.
4. Seleccionar rol `Productor`.
5. Asignar organizacion de prueba staging.
6. Asignar evento `Evento Demo Home Productor Online V4.0.1`.
7. Definir password inicial temporal.
8. Marcar cambio obligatorio.
9. Guardar usuario.
10. Login Productor.
11. Forzar cambio de contraseña.
12. Login con nueva contraseña.
13. Home Visual visible.
14. 12 tarjetas visibles con permisos completos.
15. Reset password desde Admin.
16. Password anterior rechazada.
17. Password nueva aceptada.
18. Desactivar Productor.
19. Login bloqueado.
20. Reactivar Productor.
21. Login aceptado.
22. Productor no puede crear Super Admin.
23. Tenant A no administra Tenant B.
24. `/api/users` no expone `pin_hash`.
25. Safe Mode ON.
26. Live Mode OFF.
27. Secrets exposed = 0.

## Resultado Esperado

- ADMIN USER MANAGEMENT ONLINE: PASSED
- PRODUCER ONLINE: PASSED
- PASSWORD RESET: PASSED
- DEACTIVATE/REACTIVATE: PASSED
- RBAC: PASSED
- PIN_HASH EXPOSED: 0
- SECRETS EXPOSED: 0

## Restricciones

No registrar contraseñas, hashes, tokens ni datos personales reales.
