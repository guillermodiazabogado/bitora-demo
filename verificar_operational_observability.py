from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path

def main() -> None:
    with tempfile.TemporaryDirectory(dir=Path.cwd()/"tmp") as directory:
        root=Path(directory); report=root/"observability.json"; html=root/"observability.html"
        result=subprocess.run([sys.executable,"scripts/operational_observability.py","--json",str(report),"--html",str(html),"--samples","2","--interval","0","--simulate"],text=True,capture_output=True)
        assert result.returncode == 0, result.stderr
        data=json.loads(report.read_text(encoding="utf-8")); assert len(data["series"]) == 2
        expected={"API_DOWN","DB_DOWN","ERROR_RATE_HIGH","HTTP_LATENCY_HIGH","QUEUE_BACKLOG","DEVICE_STALE","SNAPSHOT_STALE"}
        opened={item["code"] for item in data["alert_events"] if item["status"]=="open"}; resolved={item["code"] for item in data["alert_events"] if item["status"]=="resolved"}
        assert opened == expected and resolved == expected and not data["active_alerts"]
        assert all(signal["provenance"]=="simulated" for point in data["series"] for signal in point["signals"].values())
        markup=html.read_text(encoding="utf-8"); assert "Alert lifecycle" in markup and "resolved" in markup
    print("OK: observability series, provenance, seven alert rules and resolution lifecycle")
if __name__ == "__main__": main()
