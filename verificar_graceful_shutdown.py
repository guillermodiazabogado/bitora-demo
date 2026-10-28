from pathlib import Path


source = Path("server.py").read_text(encoding="utf-8")

required = (
    "import signal",
    "signal.signal(signal.SIGTERM, request_shutdown)",
    "signal.signal(signal.SIGINT, request_shutdown)",
    'threading.Thread(target=httpd.shutdown, name="bitora-http-shutdown", daemon=True).start()',
    'print(f"BITORA deteniendo por signal {int(signum)}")',
)

missing = [fragment for fragment in required if fragment not in source]
if missing:
    raise SystemExit(f"FAIL - graceful shutdown incompleto: {missing}")

print("OK - SIGTERM/SIGINT solicitan cierre HTTP controlado")
