from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path

def main():
    source=Path("scripts/operational_integrated_endurance.py").read_text(encoding="utf-8")
    for token in ("15m","60m","6h","operational_multiinstance.py","http_throughput_ops_s","infrastructure_summary","explicitly_not_exercised","atomic"):
        assert token in source,token
    with tempfile.TemporaryDirectory(dir=Path.cwd()/"tmp") as directory:
        root=Path(directory);fake=root/"fake_harness.py";report=root/"result.json";checkpoint=root/"checkpoint.json"
        fake.write_text("""import argparse,json,time\np=argparse.ArgumentParser();p.add_argument('--endurance-seconds');p.add_argument('--sample-seconds');p.add_argument('--checkpoint');p.add_argument('--report');a=p.parse_args();time.sleep(.2);telemetry={'samples':[{'postgres':{'connections_total':3},'readiness':[{'status':200}]}],'summary':{'samples':1,'readiness_200':1,'readiness_total':1}};json.dump({'ok':True,'checks':{'two_distinct_instances_ready':True},'endurance':{'attempted':20,'succeeded':20,'failures_total':0,'elapsed_seconds':2,'latency_ms':{'p95':12}},'telemetry':telemetry,'observed':{'access_events':[{'count':20}],'snapshots':[{'current_state':'OUTSIDE'}]}},open(a.report,'w'));json.dump({'status':'complete'},open(a.checkpoint,'w'))\n""",encoding="utf-8")
        proc=subprocess.run([sys.executable,"scripts/operational_integrated_endurance.py","--stage","15m","--seconds","2","--sample-seconds","0.05","--harness",str(fake),"--report",str(report),"--checkpoint",str(checkpoint)],text=True,capture_output=True)
        assert proc.returncode==0,proc.stderr
        data=json.loads(report.read_text());assert data["ok"] and data["telemetry"]["http_throughput_ops_s"]==10
        assert data["telemetry"]["infrastructure_summary"]["readiness_200"]==1
        assert data["telemetry"]["http_failures_total"]==0
        assert data["explicitly_not_exercised"]==["vouchers","lead retrieval","vehicle logistics"]
        assert data["telemetry"]["runner_samples"] and json.loads(checkpoint.read_text())["status"]=="complete"
    print("OK: integrated stages, checkpointing, telemetry and honest operation scope")
if __name__=="__main__":main()
