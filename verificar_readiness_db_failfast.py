from __future__ import annotations

import time
from pathlib import Path

import server


class OfflineProbe:
    def __enter__(self):
        raise RuntimeError("simulated database outage with secret=do-not-expose")

    def __exit__(self, *_args):
        return False


def main() -> None:
    original = server.connect_database_probe
    original_cache = dict(server.DB_PROBE_CACHE)
    calls = {"count": 0}

    def offline(*_args, **_kwargs):
        calls["count"] += 1
        return OfflineProbe()

    try:
        server.connect_database_probe = offline
        server.DB_PROBE_CACHE.update(at=0.0, value=None)
        started = time.perf_counter()
        first = server.database_probe_snapshot()
        second = server.database_probe_snapshot()
        assert time.perf_counter() - started < 0.5
        assert first["db_status"] == "offline" and not first["migrations_ok"]
        assert first["migration_detail"]["error"] == "database_unavailable"
        assert "secret" not in repr(first).lower()
        assert second == first and calls["count"] == 1

        health, health_status = server.production_health_payload()
        ready, ready_status = server.readiness_payload()
        assert health_status == 503 and health["db"] == "offline"
        assert ready_status == 503 and not ready["checks"]["database"]
        assert calls["count"] == 1, "health/readiness deben compartir cache de probe"

        nginx = (Path(__file__).parent / "deployment" / "operational-nginx.conf").read_text(encoding="utf-8")
        assert "proxy_next_upstream error timeout http_502 http_503 http_504;" in nginx
        assert "proxy_next_upstream_tries 2;" in nginx
        assert "proxy_next_upstream_timeout 4s;" in nginx
    finally:
        server.connect_database_probe = original
        server.DB_PROBE_CACHE.clear()
        server.DB_PROBE_CACHE.update(original_cache)
    print("OK - DB outage responde 503 rapido, redactado y sin tormenta de probes")


if __name__ == "__main__":
    main()
