from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def components(lockfile: Path) -> list[dict]:
    result = []
    for raw in lockfile.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", line)
        if not match:
            raise ValueError(f"LOCK_ENTRY_INVALID:{line}")
        name, version = match.groups()
        normalized = name.lower().replace("_", "-")
        result.append({"type": "library", "name": name, "version": version, "purl": f"pkg:pypi/{normalized}@{version}"})
    return sorted(result, key=lambda item: item["name"].lower())


def document() -> dict:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:00000000-0000-4000-8000-000000000000",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {"type": "application", "name": "BITORA", "version": "workspace"},
        },
        "components": components(ROOT / "requirements.lock"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
