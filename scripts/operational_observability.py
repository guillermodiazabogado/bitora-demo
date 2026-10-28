"""Dependency-free operational collector and minimal static dashboard.

Signals are explicitly labelled ``observed``, ``simulated`` or ``unavailable``.
Simulation is opt-in and intended only to verify alert transitions.
"""
from __future__ import annotations

import argparse, ctypes, json, os, time, urllib.error, urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path


RULES = {
    "API_DOWN": ("api_ok", lambda value: value is False),
    "DB_DOWN": ("db_ok", lambda value: value is False),
    "ERROR_RATE_HIGH": ("error_rate", lambda value: value is not None and value >= 0.05),
    "HTTP_LATENCY_HIGH": ("http_latency_ms", lambda value: value is not None and value >= 1000),
    "QUEUE_BACKLOG": ("queue_depth", lambda value: value is not None and value >= 100),
    "DEVICE_STALE": ("device_age_seconds", lambda value: value is not None and value >= 120),
    "SNAPSHOT_STALE": ("snapshot_age_seconds", lambda value: value is not None and value >= 60),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def memory_bytes() -> int | None:
    if os.name != "nt": return None
    class C(ctypes.Structure):
        _fields_=[("cb",ctypes.c_ulong),("faults",ctypes.c_ulong),("peak",ctypes.c_size_t),("working",ctypes.c_size_t),("a",ctypes.c_size_t),("b",ctypes.c_size_t),("c",ctypes.c_size_t),("d",ctypes.c_size_t),("page",ctypes.c_size_t),("page_peak",ctypes.c_size_t)]
    try:
        item=C(); item.cb=ctypes.sizeof(item); kernel=ctypes.WinDLL("kernel32"); psapi=ctypes.WinDLL("psapi")
        kernel.GetCurrentProcess.restype=ctypes.c_void_p; psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
        return int(item.working) if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(item),item.cb) else None
    except Exception: return None


def signal(value, provenance: str, detail: str = "") -> dict:
    assert provenance in {"observed","simulated","unavailable"}
    return {"value": value, "provenance": provenance, "detail": detail}


def http_probe(url: str) -> tuple[dict, dict]:
    if not url:
        return signal(None,"unavailable","no --http-url"), signal(None,"unavailable","no --http-url")
    started=time.perf_counter()
    try:
        with urllib.request.urlopen(url,timeout=5) as response: ok=200 <= response.status < 500
    except Exception as exc:
        return signal(False,"observed",type(exc).__name__), signal(round((time.perf_counter()-started)*1000,3),"observed")
    return signal(ok,"observed"), signal(round((time.perf_counter()-started)*1000,3),"observed")


def fixture_sample(index: int) -> dict:
    failed=index == 0
    values={"api_ok":not failed,"db_ok":not failed,"error_rate":0.12 if failed else 0.0,"http_latency_ms":1400 if failed else 80,"queue_depth":150 if failed else 0,"device_age_seconds":180 if failed else 5,"snapshot_age_seconds":90 if failed else 3,"cpu_percent":82 if failed else 20,"ram_bytes":900_000_000 if failed else 400_000_000,"postgres_connections":42 if failed else 5,"edge_online":not failed,"freshness_seconds":90 if failed else 3}
    return {key:signal(value,"simulated","deterministic alert fixture") for key,value in values.items()}


def observed_sample(http_url: str, edge_file: Path | None) -> dict:
    api,latency=http_probe(http_url); edge=signal(None,"unavailable","no --edge-file"); device=signal(None,"unavailable","no --edge-file"); snapshot=signal(None,"unavailable","no --edge-file"); queue=signal(None,"unavailable","application metric not configured")
    if edge_file:
        try:
            payload=json.loads(edge_file.read_text(encoding="utf-8")); edge=signal(bool(payload.get("online")),"observed"); device=signal(float(payload.get("device_age_seconds",0)),"observed"); snapshot=signal(float(payload.get("snapshot_age_seconds",0)),"observed"); queue=signal(int(payload.get("queue_depth",0)),"observed")
        except Exception as exc: edge=signal(None,"unavailable",type(exc).__name__)
    return {"api_ok":api,"http_latency_ms":latency,"db_ok":signal(None,"unavailable","PostgreSQL probe adapter not configured"),"error_rate":signal(None,"unavailable","application metric not configured"),"queue_depth":queue,"device_age_seconds":device,"snapshot_age_seconds":snapshot,"cpu_percent":signal(round(100*time.process_time()/max(time.monotonic(),1),3),"observed","collector process lifetime ratio"),"ram_bytes":signal(memory_bytes(),"observed" if memory_bytes() is not None else "unavailable"),"postgres_connections":signal(None,"unavailable","PostgreSQL probe adapter not configured"),"edge_online":edge,"freshness_seconds":snapshot}


def evaluate(sample: dict, active: dict[str,dict], events: list[dict], timestamp: str) -> None:
    for code,(metric,predicate) in RULES.items():
        item=sample[metric]; firing=item["provenance"] != "unavailable" and predicate(item["value"])
        if firing and code not in active:
            active[code]={"code":code,"metric":metric,"opened_at":timestamp,"status":"open","provenance":item["provenance"]}; events.append(dict(active[code]))
        elif not firing and code in active:
            resolved=active.pop(code); resolved.update({"status":"resolved","resolved_at":timestamp}); events.append(resolved)


def render_html(report: dict) -> str:
    rows=[]
    for point in report["series"]:
        cells="".join(f"<td>{escape(str(point['signals'][key]['value']))}<small>{point['signals'][key]['provenance']}</small></td>" for key in ("cpu_percent","ram_bytes","api_ok","http_latency_ms","db_ok","postgres_connections","queue_depth","edge_online","freshness_seconds"))
        rows.append(f"<tr><td>{escape(point['timestamp'])}</td>{cells}</tr>")
    alerts="".join(f"<li class='{e['status']}'>{escape(e['code'])}: {escape(e['status'])}</li>" for e in report["alert_events"])
    return "<!doctype html><meta charset='utf-8'><title>BITORA Operational Observability</title><style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:6px}small{display:block;color:#666}.open{color:#b42318}.resolved{color:#067647}</style><h1>BITORA Operational Observability</h1><p>Every value declares observed, simulated or unavailable provenance.</p><table><thead><tr><th>UTC</th><th>CPU %</th><th>RAM</th><th>API</th><th>HTTP ms</th><th>DB</th><th>PG connections</th><th>Queue</th><th>Edge</th><th>Freshness</th></tr></thead><tbody>"+"".join(rows)+"</tbody></table><h2>Alert lifecycle</h2><ul>"+alerts+"</ul>"


def collect(args) -> dict:
    active={}; events=[]; series=[]
    for index in range(args.samples):
        timestamp=now(); signals=fixture_sample(index) if args.simulate else observed_sample(args.http_url,args.edge_file)
        evaluate(signals,active,events,timestamp); series.append({"timestamp":timestamp,"signals":signals})
        if index+1 < args.samples: time.sleep(args.interval)
    return {"generated_at":now(),"mode":"simulated" if args.simulate else "observed","series":series,"alert_events":events,"active_alerts":list(active.values()),"rules":sorted(RULES)}


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--json",type=Path,required=True); parser.add_argument("--html",type=Path,required=True); parser.add_argument("--samples",type=int,default=1); parser.add_argument("--interval",type=float,default=5); parser.add_argument("--http-url",default=""); parser.add_argument("--edge-file",type=Path); parser.add_argument("--simulate",action="store_true"); args=parser.parse_args()
    if args.samples < 1 or args.interval < 0: parser.error("invalid sampling parameters")
    report=collect(args); args.json.parent.mkdir(parents=True,exist_ok=True); args.html.parent.mkdir(parents=True,exist_ok=True); args.json.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8"); args.html.write_text(render_html(report),encoding="utf-8"); print(json.dumps({"samples":len(report["series"]),"alerts":len(report["alert_events"]),"mode":report["mode"]}))
if __name__ == "__main__": main()
