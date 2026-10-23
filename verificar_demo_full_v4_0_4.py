from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server


def fetch_json(url: str) -> tuple[bool, dict]:
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return True, json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return False, {"error": str(exc)}


def fetch_text(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return True, response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return False, str(exc)


def local_prepare() -> dict:
    server.init_db()
    with server.connect() as db:
        return server.demo_full_service().prepare(db, actor="verificar_demo_full_v4_0_4")


def local_verify() -> dict:
    server.init_db()
    with server.connect() as db:
        return server.demo_full_service().verify(db)


def remote_verify(base_url: str) -> dict:
    base = base_url.rstrip("/")
    health_ok, health = fetch_json(f"{base}/health")
    ready_ok, ready = fetch_json(f"{base}/ready")
    portal_ok, portal_html = fetch_text(f"{base}/p.html")
    checks = {
        "health": health_ok and health.get("status") == "ok",
        "ready": ready_ok and ready.get("status") == "ready",
        "environment_staging": health.get("env") == "staging",
        "postgresql": health.get("db") == "online",
        "safe_mode": bool((ready.get("checks") or {}).get("safe_mode")),
        "live_mode_off": bool((ready.get("checks") or {}).get("live_mode_off")),
        "participant_home_published": portal_ok and "participant-bottom-nav" in portal_html and "Mis charlas" in portal_html,
    }
    passed = sum(1 for value in checks.values() if value)
    return {
        "ok": passed == len(checks),
        "score": f"{passed}/{len(checks)}",
        "checks": checks,
        "health": health,
        "ready": ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="BITORA V4.0.4 Demo Full verifier")
    parser.add_argument("--prepare", action="store_true", help="Prepara dataset local con datos ficticios")
    parser.add_argument("--base-url", default="", help="Valida staging online")
    args = parser.parse_args()

    payload: dict[str, object] = {"name": "BITORA V4.0.4 Demo Full Readiness"}
    if args.prepare:
        payload["prepare"] = local_prepare()
    payload["local"] = local_verify()
    if args.base_url:
        payload["remote"] = remote_verify(args.base_url)

    local_ok = bool((payload["local"] or {}).get("ok"))
    remote_ok = True if not args.base_url else bool((payload.get("remote") or {}).get("ok"))
    payload["passed"] = local_ok and remote_ok
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
