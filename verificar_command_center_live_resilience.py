from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    service = (ROOT / "backend" / "services" / "command_center.py").read_text(encoding="utf-8")
    required = [
        "if (!document.hidden) loadCommandCenter()",
        "refresh_error",
        "stale: true",
        "Datos conservados, actualizacion interrumpida",
        "const unobserved =",
        "const expired =",
        '"STALE"',
    ]
    missing = [item for item in required if item not in app]
    assert not missing, f"Command Center sin resiliencia: {missing}"
    assert '"safe_mode": "NOT_CHECKED"' in service
    assert '"live_mode": "NOT_CHECKED"' in service
    assert '"safe_mode": "ON"' not in service and '"live_mode": "OFF"' not in service
    print("OK: Command Center pausa oculto, conserva snapshot y no declara salud no observada")


if __name__ == "__main__":
    main()
