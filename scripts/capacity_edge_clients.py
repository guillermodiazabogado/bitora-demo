from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import tempfile
import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.edge_client import EdgeClient, EdgeScope


TRANSPORT_KIND = "in_memory_simulated_transport_not_http"
DEFAULT_LEVELS = (2, 5, 10, 25, 50, 100)


class MutableClock:
    """Deterministic clock used to advance Edge retry windows without sleeping."""

    def __init__(self, value: float = 100_000.0) -> None:
        self.value = value
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self.value

    def advance(self, seconds: float) -> None:
        with self._lock:
            self.value += seconds


class SimulatedTransport:
    """In-memory acknowledgement transport; deliberately performs no HTTP I/O."""

    def __init__(self) -> None:
        self.online = False
        self.received: set[str] = set()
        self.sync_calls = 0
        self._lock = threading.Lock()

    def heartbeat(self, *, scope: EdgeScope, secret: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.online:
            raise ConnectionError("simulated offline transport")
        return {"ok": True, "queue_depth": payload["queue_depth"]}

    def sync(
        self,
        *,
        scope: EdgeScope,
        secret: str,
        operations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            self.sync_calls += 1
            if not self.online:
                raise ConnectionError("simulated offline transport")
            for operation in operations:
                self.received.add(str(operation["idempotency_key"]))
        return {
            "ok": True,
            "acknowledged_operation_ids": [item["operation_id"] for item in operations],
        }


@dataclass
class DeviceRuntime:
    index: int
    database: Path
    scope: EdgeScope
    secret: str
    clock: MutableClock
    transport: SimulatedTransport
    client: EdgeClient


def _quiet_logger(device_id: int) -> logging.Logger:
    logger = logging.getLogger(f"bitora.capacity.edge.{device_id}")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    logger.setLevel(logging.CRITICAL)
    return logger


def _make_runtime(root: Path, index: int, level: int) -> DeviceRuntime:
    device_id = level * 10_000 + index + 1
    database = root / f"device-{device_id}.sqlite3"
    scope = EdgeScope(organization_id=1, event_id=level, device_id=device_id)
    secret = f"capacity-secret-{level}-{index}"
    clock = MutableClock()
    transport = SimulatedTransport()
    client = EdgeClient(
        database,
        scope=scope,
        device_secret=secret,
        signing_keys={},
        transport=transport,
        logger=_quiet_logger(device_id),
        clock=clock,
    )
    return DeviceRuntime(index, database, scope, secret, clock, transport, client)


def _enqueue_offline(runtime: DeviceRuntime, operation_count: int) -> int:
    for operation_index in range(operation_count):
        operation = runtime.client.enqueue(
            "VALIDATE_ACCESS",
            {
                "token_hash": f"synthetic-{runtime.scope.device_id}-{operation_index}",
                "direction": "ENTRY" if operation_index % 2 == 0 else "EXIT",
            },
            local_decision={"decision": "ALLOW", "reason_code": "SYNTHETIC_CAPACITY_TEST"},
            idempotency_key=f"capacity-{runtime.scope.device_id}-{operation_index}",
            correlation_id=f"capacity-{runtime.scope.device_id}-{operation_index}",
        )
        if operation["device_sequence"] != operation_index + 1:
            raise AssertionError("secuencia local no monotona")

    # Exercise the actual durable retry path once while the simulated link is down.
    sent = 0
    while sent < operation_count:
        result = runtime.client.sync(limit=min(250, operation_count - sent))
        if result["ok"] or result["acknowledged"]:
            raise AssertionError("el transporte offline reconocio operaciones")
        sent += int(result["sent"])
    # Make every first retry eligible only after all original operations have
    # received exactly one offline attempt; otherwise early sequences could
    # starve later PENDING rows.
    runtime.clock.advance(0.5)
    return sent


def _restart(runtime: DeviceRuntime) -> None:
    expected_depth = runtime.client.queue_depth
    expected_sequence = runtime.client.last_sequence
    runtime.client.close()
    runtime.client = EdgeClient(
        runtime.database,
        scope=runtime.scope,
        device_secret=runtime.secret,
        signing_keys={},
        transport=runtime.transport,
        logger=_quiet_logger(runtime.scope.device_id),
        clock=runtime.clock,
    )
    if runtime.client.queue_depth != expected_depth or runtime.client.last_sequence != expected_sequence:
        raise AssertionError("el reinicio no preservo cola o secuencia")


def _drain(runtime: DeviceRuntime) -> dict[str, int]:
    runtime.transport.online = True
    runtime.clock.advance(300.0)
    guard = 0
    while runtime.client.queue_depth:
        result = runtime.client.sync(limit=250)
        if not result["ok"]:
            runtime.clock.advance(300.0)
        guard += 1
        if guard > 100_000:
            raise AssertionError("la cola no pudo vaciarse")

    with sqlite3.connect(runtime.database) as db:
        created = int(db.execute("SELECT COUNT(*) FROM operations").fetchone()[0])
        acked = int(db.execute("SELECT COUNT(*) FROM operations WHERE status='ACKED'").fetchone()[0])
        pending = int(db.execute("SELECT COUNT(*) FROM operations WHERE status<>'ACKED'").fetchone()[0])
        retries = int(db.execute("SELECT COALESCE(SUM(attempts),0) FROM operations").fetchone()[0])
    runtime.client.close()
    return {
        "created": created,
        "acked": acked,
        "pending": pending,
        "retries": retries,
        "received_unique": len(runtime.transport.received),
        "sync_calls": runtime.transport.sync_calls,
    }


def _rss_bytes() -> int | None:
    try:
        import psutil  # type: ignore[import-not-found]

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except (ImportError, OSError):
        return None


def run_level(root: Path, level: int, operations_per_device: int) -> dict[str, Any]:
    level_root = root / f"level-{level}"
    level_root.mkdir(parents=True, exist_ok=True)
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    rss_started = _rss_bytes()
    tracemalloc.reset_peak()

    runtimes = [_make_runtime(level_root, index, level) for index in range(level)]
    workers = min(level, max(2, min(32, os.cpu_count() or 2)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        offline_sent = list(executor.map(lambda item: _enqueue_offline(item, operations_per_device), runtimes))

    pending_before_reconnect = sum(runtime.client.queue_depth for runtime in runtimes)
    # Restart one quarter of the fleet (at least one) while every device is offline.
    restarted = 0
    for runtime in runtimes:
        if runtime.index % 4 == 0:
            _restart(runtime)
            restarted += 1

    drain_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        device_results = list(executor.map(_drain, runtimes))
    drain_seconds = time.perf_counter() - drain_started

    created = sum(item["created"] for item in device_results)
    acked = sum(item["acked"] for item in device_results)
    pending = sum(item["pending"] for item in device_results)
    retries = sum(item["retries"] for item in device_results)
    received_unique = sum(item["received_unique"] for item in device_results)
    lost = created - acked - pending
    wall_seconds = time.perf_counter() - wall_started
    _, traced_peak = tracemalloc.get_traced_memory()
    rss_finished = _rss_bytes()
    expected = level * operations_per_device
    ok = (
        created == expected
        and pending_before_reconnect == expected
        and acked == expected
        and pending == 0
        and lost == 0
        and received_unique == expected
        and retries >= expected
    )
    return {
        "ok": ok,
        "devices": level,
        "operations_per_device": operations_per_device,
        "created": created,
        "pending_before_reconnect": pending_before_reconnect,
        "acked": acked,
        "pending_after_drain": pending,
        "lost": lost,
        "retries": retries,
        "offline_attempted": sum(offline_sent),
        "restarted_devices": restarted,
        "sync_calls": sum(item["sync_calls"] for item in device_results),
        "drain_seconds": round(drain_seconds, 6),
        "drain_operations_per_second": round(acked / drain_seconds, 3) if drain_seconds else None,
        "wall_seconds": round(wall_seconds, 6),
        "cpu_seconds": round(time.process_time() - cpu_started, 6),
        "python_traced_peak_bytes": int(traced_peak),
        "process_rss_start_bytes": rss_started,
        "process_rss_end_bytes": rss_finished,
    }


def parse_levels(raw: str) -> list[int]:
    try:
        values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--levels requiere enteros separados por coma") from exc
    if not values or any(value <= 0 or value > 100 for value in values):
        raise argparse.ArgumentTypeError("--levels admite valores entre 1 y 100")
    return list(dict.fromkeys(values))


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark local reproducible de colas Edge SQLite con transporte simulado (NO HTTP)."
    )
    parser.add_argument("--levels", default=",".join(map(str, DEFAULT_LEVELS)), help="Dispositivos: lista separada por comas")
    parser.add_argument("--operations-per-device", type=int, default=100)
    parser.add_argument("--report", type=Path, help="Ruta opcional del informe JSON")
    parser.add_argument("--smoke", action="store_true", help="Ejecuta niveles 2/5 con 10 operaciones por dispositivo")
    args = parser.parse_args()

    if args.operations_per_device <= 0:
        parser.error("--operations-per-device debe ser positivo")
    levels = [2, 5] if args.smoke else parse_levels(args.levels)
    operations_per_device = 10 if args.smoke else args.operations_per_device

    tracemalloc.start()
    started = time.time()
    temp_parent = Path.cwd() / "tmp"
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bitora-capacity-edge-", dir=temp_parent, ignore_cleanup_errors=True) as root:
        results = [run_level(Path(root), level, operations_per_device) for level in levels]
    payload = {
        "ok": all(item["ok"] for item in results),
        "benchmark": "BITORA Edge independent durable queues",
        "transport": TRANSPORT_KIND,
        "transport_warning": "Software simulation only; no HTTP, physical device, reader or network was certified.",
        "methodology": {
            "queue": "one independent SQLite/WAL database and EdgeScope per virtual device",
            "offline": "enqueue plus one failed sync attempt for every operation",
            "restart": "one quarter of clients recreated over the same durable database",
            "reconnect": "simulated in-memory acknowledgements, batches up to 250",
            "load_model": "closed fleet; concurrent device workers",
        },
        "started_epoch_seconds": started,
        "duration_seconds": round(time.time() - started, 6),
        "levels": levels,
        "operations_per_device": operations_per_device,
        "results": results,
    }
    if args.report:
        write_report(args.report, payload)
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
