"""Short safe gate for endurance profile configuration and telemetry."""
from __future__ import annotations
import subprocess, sys, tempfile
from pathlib import Path
from scripts.operational_endurance_profiles import PROFILES, STAGES

def main() -> None:
    assert set(PROFILES) == {"A","B","C"} and STAGES == {"15m":900,"60m":3600,"6h":21600}
    assert [PROFILES[key].participants for key in ("A","B","C")] == [500,3000,10000]
    assert [PROFILES[key].devices for key in ("A","B","C")] == [4,12,24]
    source=Path("scripts/operational_endurance_profiles.py").read_text(encoding="utf-8")
    for token in ("cpu_percent","rss_bytes","connections_opened_total","db_bytes","throughput_ops_s","atomic_json","idempotent_replay"):
        assert token in source, token
    with tempfile.TemporaryDirectory(dir=Path.cwd()/"tmp") as directory:
        report=Path(directory)/"report.json"; checkpoint=Path(directory)/"checkpoint.json"
        proc=subprocess.run([sys.executable,"scripts/operational_endurance_profiles.py","--profile","A","--stage","15m","--seconds","8","--participant-limit","25","--sample-seconds","0.5","--checkpoint-seconds","0.5","--report",str(report),"--checkpoint",str(checkpoint)],text=True,capture_output=True)
        assert proc.returncode == 0, proc.stderr[-2000:]
        import json
        result=json.loads(report.read_text(encoding="utf-8"))
        assert result["ok"] and result["duration_override_seconds"] == 8
        assert result["profile_assumptions"]["participants"] == 500 and result["participants_loaded"] == 25
        assert result["mix"]["access"] > 0 and result["mix"]["reads"] > 0 and result["mix"]["idempotent_replays"] > 0
        assert result["metrics"]["samples"] and result["metrics"]["rss_final_bytes"] > 0
        assert json.loads(checkpoint.read_text(encoding="utf-8"))["status"] == "complete"
    print("OK: endurance profiles A/B/C, functional mix, telemetry and checkpoints")
if __name__ == "__main__": main()
