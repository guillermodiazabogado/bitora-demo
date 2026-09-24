# BITORA Hetzner VPS Deployment

This deployment is for a small always-on staging/demo server used for BITORA validation and Endurance 24H.

It is intentionally cheaper and simpler than Render paid plans:

- one VPS;
- Docker Compose;
- PostgreSQL in the VPS;
- Caddy for HTTPS;
- R2 for persistent files/certificates;
- Safe Mode on;
- Live Mode off.

## Recommended VPS

Hetzner Cloud `CX23` or equivalent:

- 2 vCPU;
- 4 GB RAM;
- Ubuntu 24.04 LTS;
- IPv4 enabled.

## First Server Bootstrap

Run on the VPS as `root`:

```bash
curl -fsSL https://raw.githubusercontent.com/guillermodiazabogado/bitora-demo/chore/final-endurance-certification/deployment/hetzner/bootstrap-ubuntu.sh -o /root/bootstrap-bitora.sh
bash /root/bootstrap-bitora.sh
```

Clone the repo:

```bash
cd /opt
git clone https://github.com/guillermodiazabogado/bitora-demo.git bitora
cd /opt/bitora
git checkout chore/final-endurance-certification
```

Configure environment:

```bash
cp deployment/hetzner/.env.example deployment/hetzner/.env
nano deployment/hetzner/.env
```

Generate secrets on the VPS:

```bash
openssl rand -hex 32
openssl rand -hex 32
openssl rand -base64 32
openssl rand -hex 24
```

Set at least:

- `BITORA_DOMAIN`;
- `BASE_URL`;
- `BITORA_PUBLIC_URL`;
- `BITORA_ALLOWED_HOSTS`;
- `BITORA_CORS_ORIGINS`;
- `POSTGRES_PASSWORD`;
- `SECRET_KEY`;
- `SESSION_SECRET`;
- `BITORA_INTEGRATION_ENCRYPTION_KEY`;
- `BITORA_HEALTH_TOKEN`;
- `BITORA_ADMIN_BOOTSTRAP_USER`;
- `BITORA_ADMIN_BOOTSTRAP_PASSWORD`;
- R2 credentials.

## Deploy

```bash
bash deployment/hetzner/deploy.sh
```

## Validate

```bash
curl -i https://YOUR_DOMAIN/health
curl -i https://YOUR_DOMAIN/ready
docker compose -f deployment/hetzner/docker-compose.yml --env-file deployment/hetzner/.env ps
```

Expected:

- `/health` HTTP 200;
- `/ready` HTTP 200;
- env `staging`;
- PostgreSQL online;
- storage backend `r2`;
- Safe Mode on;
- Live Mode off;
- jobs pending 0;
- jobs failed 0.

## Endurance

Only start Endurance after `/health` and `/ready` are stable:

```bash
python tools/endurance_r2_24h_runner.py --base-url https://YOUR_DOMAIN --event-id 7
```

After 24 hours:

```bash
python tools/verify_endurance_r2_final.py artifacts/endurance/<RUN_ID>
```

Do not mark `endurance_24h` as `PASSED` until the independent verifier passes.
