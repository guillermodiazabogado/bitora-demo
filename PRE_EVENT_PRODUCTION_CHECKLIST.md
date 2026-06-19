# BITORA - Checklist productivo previo al evento

## Infraestructura

- [ ] `/health` responde `status=ok`.
- [ ] `APP_ENV=production`.
- [ ] `BASE_URL` usa HTTPS.
- [ ] PostgreSQL online, migraciones e indices verificados.
- [ ] Pool de conexiones dimensionado.
- [ ] Plan con memoria suficiente; no usar Render Free para evento real.
- [ ] Storage persistente disponible.

## Recuperacion

- [ ] Backup completo reciente.
- [ ] Restauracion probada.
- [ ] Retencion confirmada.
- [ ] Copia externa o snapshot del proveedor.
- [ ] Plan de contingencia disponible sin depender de Internet.

## Seguridad

- [ ] Secretos solamente en variables de entorno.
- [ ] Usuarios y roles revisados.
- [ ] Webhooks validados.
- [ ] Logs sin tokens ni DSN.
- [ ] Endpoints administrativos protegidos.

## Operacion

- [ ] Evento y landing revisados.
- [ ] Inscripcion completa probada.
- [ ] Recepcion y busqueda probadas.
- [ ] QR valido, repetido e invalido probados.
- [ ] Portal participante probado.
- [ ] Pantalla publica probada.
- [ ] Sala de Control y NOC probados.
- [ ] Operadores capacitados y terminales cargadas.
