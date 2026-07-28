# RELEASE_CANDIDATE_FREEZE_POLICY

## Regla Central

El tag `bitora-v1.0.0-rc.1` es inmutable.

## Prohibido

- Reescribir historia.
- Force push sobre el tag.
- Mover el tag.
- Agregar funcionalidades al commit congelado.
- Cambiar dependencias.
- Cambiar migraciones.
- Cambiar imagenes Docker sin nueva RC.
- Cambiar reportes sin trazabilidad.

## Permitido

- Correccion documental trazable.
- Correccion critica mediante nueva RC.
- Parche de seguridad mediante rama hotfix y nueva RC.
- Correccion operativa con recertificacion del area afectada.

## Bug Critico

1. No mover `bitora-v1.0.0-rc.1`.
2. Crear rama hotfix.
3. Corregir.
4. Ejecutar regresion.
5. Crear `bitora-v1.0.0-rc.2`.
6. Mantener `rc.1` intacta.
