# V4.3 Issuance Flow

1. Validar feature flag.
2. Validar permiso backend.
3. Validar tenant/evento/participante.
4. Validar tipo.
5. Validar version publicada.
6. Validar decision efectiva V4.2 si corresponde.
7. Reservar numero.
8. Crear emision `PROCESSING`.
9. Renderizar PDF.
10. Guardar en storage.
11. Calcular hash.
12. Crear token de verificacion.
13. Auditar.
14. Marcar `ISSUED`.

No se marca `ISSUED` si el documento falla.
