from pathlib import Path


compose = Path("docker-compose.operational.yml").read_text(encoding="utf-8")
nginx = Path("deployment/operational-nginx.conf").read_text(encoding="utf-8")
monitor = Path("scripts/operational_monitor.py").read_text(encoding="utf-8")

checks = {
    "postgres16": "postgres:16-alpine" in compose,
    "two_instances": "app1:" in compose and "app2:" in compose,
    "no_plain_secret": "BITORA_OP_POSTGRES_PASSWORD:?" in compose,
    "safe_mode": 'BITORA_SAFE_MODE: "true"' in compose,
    "live_off": 'BITORA_LIVE_MODE: "false"' in compose,
    "healthcheck": "/ready" in compose,
    "non_public_bind": '"127.0.0.1:18787:8080"' in compose,
    "load_balancer": "least_conn" in nginx and "app1:8787" in nginx and "app2:8787" in nginx,
    "monitor_health": '"/health"' in monitor and '"/ready"' in monitor,
    "monitor_resources": '"stats", "--no-stream"' in monitor,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit(f"FAIL - staging operacional incompleto: {failed}")
print("OK - staging local aislado, balanceado y observable")
