# BITORA Staging Setup

## Preparacion

1. Copiar `.env.staging.example` como `.env.staging`.
2. Cambiar passwords y destinatarios de prueba.
3. Confirmar que `APP_ENV=staging`.
4. Confirmar que `EMAIL_SAFE_MODE=true`.
5. Confirmar que `WHATSAPP_SAFE_MODE=true`.
6. Confirmar que no se usan credenciales productivas.

## Levantar staging local

```bash
docker compose -f docker-compose.staging.yml up --build
```

## Verificar salud

```bash
curl http://localhost:8788/health
```

## Ejecutar certificacion standard

```bash
python run_bitora_supertest.py --standard
```

## Ejecutar release

```bash
python run_bitora_supertest.py --release
```

## Ejecutar disaster

```bash
python run_bitora_supertest.py --disaster
```

## Ejecutar endurance

```bash
python run_bitora_supertest.py --endurance --hours 24
```

## Destruir staging local

```bash
docker compose -f docker-compose.staging.yml down -v
```

## Nota

El archivo `.env.staging` no debe subirse a Git.
