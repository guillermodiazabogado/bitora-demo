"""Stage runner for the real HTTP + PostgreSQL + two-instance harness."""
from __future__ import annotations
import argparse, ctypes, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGES={"15m":900,"60m":3600,"6h":21600}

def utc_now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def atomic(path:Path,payload:dict):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8"); tmp.replace(path)

def process_rss(pid:int)->int|None:
    if os.name != "nt": return None
    class C(ctypes.Structure):
        _fields_=[("cb",ctypes.c_ulong),("faults",ctypes.c_ulong),("peak",ctypes.c_size_t),("working",ctypes.c_size_t),("a",ctypes.c_size_t),("b",ctypes.c_size_t),("c",ctypes.c_size_t),("d",ctypes.c_size_t),("page",ctypes.c_size_t),("page_peak",ctypes.c_size_t)]
    PROCESS_QUERY_LIMITED_INFORMATION=0x1000
    try:
        k=ctypes.WinDLL("kernel32"); p=ctypes.WinDLL("psapi"); k.OpenProcess.restype=ctypes.c_void_p
        handle=k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,False,pid)
        if not handle:return None
        item=C();item.cb=ctypes.sizeof(item);p.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
        value=int(item.working) if p.GetProcessMemoryInfo(handle,ctypes.byref(item),item.cb) else None;k.CloseHandle(handle);return value
    except Exception:return None

def parse_args():
    p=argparse.ArgumentParser();p.add_argument("--stage",choices=STAGES,required=True);p.add_argument("--seconds",type=int,help="smoke-only override");p.add_argument("--report",type=Path,required=True);p.add_argument("--checkpoint",type=Path,required=True);p.add_argument("--sample-seconds",type=float,default=30);p.add_argument("--harness",type=Path,default=ROOT/"scripts"/"operational_multiinstance.py");return p.parse_args()

def run(args)->dict:
    duration=args.seconds if args.seconds is not None else STAGES[args.stage]
    if duration < 1 or args.sample_seconds <= 0: raise ValueError("invalid duration")
    child_report=args.report.with_suffix(".harness.json")
    command=[sys.executable,str(args.harness),"--endurance-seconds",str(duration),"--report",str(child_report)]
    started=time.monotonic();started_at=utc_now();samples=[]
    process=subprocess.Popen(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        while process.poll() is None:
            elapsed=time.monotonic()-started
            sample={"timestamp":utc_now(),"elapsed_seconds":round(elapsed,3),"runner_rss_bytes":process_rss(process.pid),"harness_running":True}
            samples.append(sample)
            atomic(args.checkpoint,{"status":"running","stage":args.stage,"nominal_seconds":STAGES[args.stage],"duration_seconds":duration,"last_sample":sample,"samples_collected":len(samples)})
            time.sleep(min(args.sample_seconds,max(.05,duration/20)))
        stdout,stderr=process.communicate(timeout=30)
    finally:
        if process.poll() is None: process.kill()
    if process.returncode != 0 or not child_report.exists(): raise RuntimeError(f"integrated harness failed: {stderr[-1500:]}")
    harness=json.loads(child_report.read_text(encoding="utf-8")); endurance=harness.get("endurance",{}); elapsed=time.monotonic()-started
    attempted=int(endurance.get("attempted",0)); succeeded=int(endurance.get("succeeded",0))
    result={"ok":bool(harness.get("ok")),"stage":args.stage,"nominal_duration_seconds":STAGES[args.stage],"duration_override_seconds":args.seconds,"started_at":started_at,"finished_at":utc_now(),"elapsed_seconds":round(elapsed,3),"architecture":"real HTTP + PostgreSQL 16 + two application instances","supported_operation_mix":["authentication and cross-instance session","event visibility read","access ENTRY/EXIT","anti-passback concurrency","idempotent access replay"],"explicitly_not_exercised":["vouchers","lead retrieval","vehicle logistics"],"telemetry":{"samples":samples,"http_attempted":attempted,"http_succeeded":succeeded,"http_throughput_ops_s":round(succeeded/max(float(endurance.get("elapsed_seconds",0) or 0),.001),3),"http_latency_ms":endurance.get("latency_ms"),"postgres_access_events":harness.get("observed",{}).get("access_events"),"postgres_connections":"unavailable: base harness does not expose pg_stat_activity","database_state":harness.get("observed",{}).get("snapshots"),"edge":"not in scope"},"harness_checks":harness.get("checks",{}),"harness_report":str(child_report),"limitations":["CPU/RAM samples cover the orchestrated harness process; container resource telemetry requires a future Docker stats adapter.","No voucher/lead/vehicle traffic is synthesized without a proven HTTP contract."]}
    atomic(args.checkpoint,{"status":"complete",**result});atomic(args.report,result);return result

def main():
    args=parse_args();result=run(args);print(json.dumps(result));raise SystemExit(0 if result["ok"] else 2)
if __name__=="__main__":main()
