from __future__ import annotations

import json
from pathlib import Path

import server


def main() -> None:
    root = Path(__file__).resolve().parent
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    manifest = json.loads((root / "release-manifest.json").read_text(encoding="utf-8"))
    migrations = sorted((root / "backend" / "migrations").glob("*.sql"))
    if not version or server.APP_VERSION != version:
        raise AssertionError((version, server.APP_VERSION))
    if manifest["latest_migration"] != migrations[-1].name:
        raise AssertionError((manifest["latest_migration"], migrations[-1].name))
    for field in ("dependency_lock", "sbom_generator", "postgres_certifier", "release_gate"):
        if not (root / manifest[field]).exists():
            raise AssertionError({field: manifest[field]})
    print(f"P2 release manifest and single version source: OK ({version})")


if __name__ == "__main__":
    main()
