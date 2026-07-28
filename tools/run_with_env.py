from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def load_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def main() -> int:
    if len(sys.argv) < 3:
        print("Uso: python tools/run_with_env.py <env-file> <script.py>")
        return 2
    env_path = Path(sys.argv[1])
    script = Path(sys.argv[2])
    if not env_path.exists():
        print(f"No existe env file: {env_path}")
        return 2
    if not script.exists():
        print(f"No existe script: {script}")
        return 2
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    load_env(env_path)
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
