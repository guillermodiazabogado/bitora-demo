"""Parameterized BITORA endurance profiles with reproducible checkpoints.

Stages describe the certification duration; ``--seconds`` exists only for
smoke verification and is recorded as an override in the result.
"""
from __future__ import annotations

import argparse, ctypes, json, os, shutil, tempfile, time, tracemalloc
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import server


@dataclass(frozen=True)
class Profile:
    participants: int
    doors: int
    devices: int
    operators: int
    pause_ms: int
    access_weight: int
    read_weight: int
    replay_weight: int


PROFILES = {
    "A": Profile(500, 2, 4, 2, 40, 70, 20, 10),
    "B": Profile(3000, 6, 12, 6, 10, 75, 15, 10),
    "C": Profile(10000, 12, 24, 12, 0, 80, 10, 10),
}
STAGES = {"15m": 900, "60m": 3600, "6h": 21600}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rss_bytes() -> int | None:
    if os.name != "nt":
        try:
            import resource
            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
        except Exception:
            return None
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    try:
        counters = Counters(); counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        handle = kernel32.GetCurrentProcess()
        return int(counters.WorkingSetSize) if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb) else None
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BITORA endurance profiles A/B/C")
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--seconds", type=float, help="Smoke-only duration override")
    parser.add_argument("--participant-limit", type=int, help="Smoke-only dataset cap; recorded in evidence")
    parser.add_argument("--sample-seconds", type=float, default=30)
    parser.add_argument("--checkpoint-seconds", type=float, default=300)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    return parser.parse_args()


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(args: argparse.Namespace) -> dict:
    profile = PROFILES[args.profile]
    participant_count = min(profile.participants, args.participant_limit) if args.participant_limit else profile.participants
    nominal = STAGES[args.stage]
    duration = float(args.seconds if args.seconds is not None else nominal)
    if duration <= 0 or args.sample_seconds <= 0 or args.checkpoint_seconds <= 0:
        raise ValueError("durations must be positive")
    temp_parent = ROOT / "tmp"; temp_parent.mkdir(exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-endurance-profile-", dir=temp_parent))
    old_db, old_backup = server.DB_PATH, server.BACKUP_DIR
    started_wall, started_cpu = time.monotonic(), time.process_time()
    started_at = utc_now(); operations = reads = replays = failures = connections = 0
    samples: list[dict] = []; last_sample = last_checkpoint = started_wall; last_ops = 0
    tracemalloc.start()
    try:
        server.DB_PATH = temp_root / "endurance.sqlite3"; server.BACKUP_DIR = temp_root / "backups"
        server.init_db(); server.seed_if_empty()
        tokens = []
        with server.connect() as db:
            connections += 1
            event_id = int(db.execute("SELECT id FROM events ORDER BY id LIMIT 1").fetchone()["id"])
            for index in range(participant_count):
                item = server.register_accreditation(db, event_id, {"first_name":"Endurance", "last_name":str(index), "email":f"profile-{args.profile}-{index}@bitora.test", "type":"General", "actor":"endurance-profile"})
                tokens.append(str(item["token"]))
            server.set_access_state_enforcement(db, event_id, enabled=True, actor="endurance-profile")
        states = {token: "OUTSIDE" for token in tokens}; index = 0; last_request = None
        while time.monotonic() - started_wall < duration:
            slot = index % 100; token = tokens[index % len(tokens)]
            try:
                if slot < profile.access_weight:
                    direction = "ENTRY" if states[token] == "OUTSIDE" else "EXIT"
                    key = f"profile-{args.profile}-{operations}"
                    with server.DB_LOCK, server.connect() as db:
                        connections += 1; db.execute("BEGIN IMMEDIATE")
                        result = server.enforced_access_validation(db, token=token, operator="Endurance Profile", checkpoint=f"Profile {args.profile}", activity_id=0, direction=direction, correlation_id=key, idempotency_key=key, data={}, event_scope=server.access_event_scope(db, token)); db.execute("COMMIT")
                    if result.get("result") != "granted": raise RuntimeError(str(result))
                    states[token] = "INSIDE" if direction == "ENTRY" else "OUTSIDE"; operations += 1
                    last_request = (token, direction, key)
                elif slot < profile.access_weight + profile.read_weight:
                    with server.connect() as db:
                        connections += 1; db.execute("SELECT COUNT(*) FROM enterprise_access_events WHERE event_id = ?", (event_id,)).fetchone()
                    reads += 1
                elif last_request:
                    token_r, direction_r, key_r = last_request
                    with server.connect() as db:
                        connections += 1
                        result = server.enforced_access_validation(db, token=token_r, operator="Endurance Profile", checkpoint=f"Profile {args.profile}", activity_id=0, direction=direction_r, correlation_id=key_r, idempotency_key=key_r, data={}, event_scope=server.access_event_scope(db, token_r))
                    if not result.get("idempotent_replay"): raise RuntimeError("replay was not idempotent")
                    replays += 1
            except Exception:
                failures += 1
                if failures >= 10: break
            index += 1
            now = time.monotonic()
            if now - last_sample >= args.sample_seconds:
                heap, peak = tracemalloc.get_traced_memory(); delta = now - last_sample
                samples.append({"at_seconds":round(now-started_wall,3), "cpu_percent":round(100*(time.process_time()-started_cpu)/max(now-started_wall,.001),2), "rss_bytes":rss_bytes(), "python_heap_bytes":heap, "python_heap_peak_bytes":peak, "db_bytes":server.DB_PATH.stat().st_size if server.DB_PATH.exists() else 0, "connections_opened_total":connections, "throughput_ops_s":round((operations+reads+replays-last_ops)/delta,3)})
                last_ops = operations+reads+replays; last_sample = now
            if args.checkpoint and now - last_checkpoint >= args.checkpoint_seconds:
                atomic_json(args.checkpoint, {"status":"running", "profile":args.profile, "stage":args.stage, "elapsed_seconds":round(now-started_wall,3), "operations":operations, "reads":reads, "replays":replays, "failures":failures, "last_sample":samples[-1] if samples else None})
                last_checkpoint = now
            if profile.pause_ms: time.sleep(profile.pause_ms/1000)
        elapsed = time.monotonic()-started_wall
        with server.connect() as db:
            connections += 1; integrity = db.execute("PRAGMA integrity_check").fetchone()[0]; persisted = int(db.execute("SELECT COUNT(*) FROM enterprise_access_events").fetchone()[0])
        result = {"ok":failures==0 and integrity=="ok" and persisted==operations, "profile":args.profile, "stage":args.stage, "nominal_duration_seconds":nominal, "duration_override_seconds":args.seconds, "profile_assumptions":{"participants":profile.participants,"doors":profile.doors,"devices":profile.devices,"operators":profile.operators}, "participants_loaded":participant_count, "participant_limit_override":args.participant_limit, "started_at":started_at, "finished_at":utc_now(), "elapsed_seconds":round(elapsed,3), "mix":{"access":operations,"reads":reads,"idempotent_replays":replays}, "persisted_access_events":persisted, "failures":failures, "metrics":{"samples":samples,"connections_opened_total":connections,"throughput_ops_s":round((operations+reads+replays)/max(elapsed,.001),3),"cpu_seconds":round(time.process_time()-started_cpu,3),"rss_final_bytes":rss_bytes(),"db_final_bytes":server.DB_PATH.stat().st_size}, "database_integrity":integrity, "scope":"isolated SQLite functional pre-gate; not integrated HTTP/PostgreSQL capacity evidence"}
        if args.checkpoint: atomic_json(args.checkpoint, {"status":"complete", **result})
        return result
    finally:
        tracemalloc.stop(); server.DB_PATH, server.BACKUP_DIR = old_db, old_backup; shutil.rmtree(temp_root, ignore_errors=True)


def main() -> None:
    args=parse_args(); result=run(args); atomic_json(args.report,result); print(json.dumps(result)); raise SystemExit(0 if result["ok"] else 1)
if __name__ == "__main__": main()
