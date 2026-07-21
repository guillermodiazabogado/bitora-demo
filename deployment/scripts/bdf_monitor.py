from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


LOG_DIR = Path("/bitora/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "monitor.jsonl"


def main() -> None:
    while True:
        payload = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "env": "staging"}
        try:
            with urllib.request.urlopen("http://bitora-staging-app:8787/health", timeout=5) as response:
                payload["health"] = json.loads(response.read().decode("utf-8"))
                payload["ok"] = True
        except Exception as exc:
            payload["ok"] = False
            payload["error"] = str(exc)[:300]
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        time.sleep(30)


if __name__ == "__main__":
    main()
