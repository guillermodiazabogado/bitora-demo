from __future__ import annotations

from scripts.generate_sbom import components, ROOT


def main() -> None:
    items = components(ROOT / "requirements.lock")
    if len(items) != 18 or len({item["purl"] for item in items}) != len(items):
        raise AssertionError(items)
    if not all(item["purl"].startswith("pkg:pypi/") for item in items):
        raise AssertionError("Invalid PURL")
    print("P2 CycloneDX SBOM source: OK (18 locked components)")


if __name__ == "__main__":
    main()
