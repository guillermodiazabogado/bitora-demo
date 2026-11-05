# Manual de despliegue de staging — BITORA 5.8.2

## Alcance

Este paquete despliega PostgreSQL 16, dos instancias BITORA y un proxy Caddy. La configuración incluida está destinada a validación local aislada. Un destino externo requiere autorización, DNS, certificado TLS y secretos propios del entorno.

## Requisitos

- Docker Engine y Compose actuales.
- 4 CPU y 4 GiB de RAM disponibles como mínimo para el ensayo.
- Puerto TCP local 9443 libre.
- SHA de código funcional certificado: `33c13cf0aaf79baae4e28d2603cb0732a10dbde2`.
- Variables secretas fuertes generadas fuera del repositorio: contraseñas PostgreSQL, secretos de sesión/aplicación, firmas y credencial bootstrap.

Nunca copiar `.env.phase7.example` como secreto real ni versionar un `.env` poblado.

## Validación local reproducible

Desde la raíz del repositorio:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/launch_phase7_local.ps1
```

El lanzador genera secretos efímeros en memoria, los transmite a WSL mediante `WSLENV` y ejecuta el orquestador. Los resultados quedan en `auditoria/bitora_5_8_2_phase_7/`.

Consulta manual, sin mostrar configuración sensible:

```bash
docker compose -f deployment/phase7/docker-compose.phase7.yml ps
curl -k --resolve bitora.localhost:9443:127.0.0.1 https://bitora.localhost:9443/ready
```

## Adaptación a un staging externo autorizado

1. Congelar SHA, imagen y `requirements.lock`.
2. Reemplazar `bitora.localhost` por el dominio autorizado.
3. Sustituir `tls internal` por un certificado válido del entorno.
4. Usar un gestor de secretos; no interpolar valores en archivos versionados.
5. Mantener PostgreSQL y las aplicaciones sin puertos públicos.
6. Restringir ingreso al proxy mediante firewall/VPN.
7. Ejecutar migraciones con backup previo y una ventana aprobada.
8. Repetir healthchecks, seguridad, restore y smoke tests en ese destino.

## Parada segura

```bash
docker compose -f deployment/phase7/docker-compose.phase7.yml stop
```

`stop` conserva volúmenes. No ejecutar `down -v` sobre un entorno con datos que deban preservarse.

