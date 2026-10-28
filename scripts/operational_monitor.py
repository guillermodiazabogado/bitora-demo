from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def fetch_json(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except Exception as exc:
        return 0, {"error": type(exc).__name__}


def docker_stats() -> list[dict]:
    command = [
        "docker", "compose", "-f", "docker-compose.operational.yml", "stats", "--no-stream",
        "--format", "json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode:
        return [{"error": "docker_stats_failed", "returncode": completed.returncode}]
    rows = []
    for line in completed.stdout.splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor operacional aislado de BITORA")
    parser.add_argument("--base-url", default="http://127.0.0.1:18787")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(1, args.seconds)
    failures = 0
    samples = 0
    with output.open("w", encoding="utf-8") as handle:
        while time.monotonic() < deadline:
            started = time.perf_counter()
            health_status, health = fetch_json(args.base_url + "/health")
            ready_status, ready = fetch_json(args.base_url + "/ready")
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            ok = health_status == 200 and ready_status == 200
            failures += 0 if ok else 1
            samples += 1
            sample = {
                "at": datetime.now(timezone.utc).isoformat(),
                "ok": ok,
                "latency_ms": elapsed_ms,
                "health_status": health_status,
                "ready_status": ready_status,
                "health": health,
                "ready": ready,
                "containers": docker_stats(),
            }
            handle.write(json.dumps(sample, sort_keys=True) + "\n")
            handle.flush()
            time.sleep(max(0.1, args.interval))
    print(json.dumps({"ok": failures == 0, "samples": samples, "failures": failures, "output": str(output)}))
    raise SystemExit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()

