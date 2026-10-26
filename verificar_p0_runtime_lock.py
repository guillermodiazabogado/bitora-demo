from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def names(path: Path) -> dict[str, str]:
    result = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*(.*)", line)
        if not match:
            raise AssertionError(line)
        result[match.group(1).lower().replace("_", "-")] = match.group(2)
    return result


def main() -> None:
    requirements = names(ROOT / "requirements.txt")
    locked = names(ROOT / "requirements.lock")
    missing = sorted(set(requirements) - set(locked))
    if missing:
        raise AssertionError({"missing_direct_dependencies": missing})
    unpinned = sorted(name for name, spec in locked.items() if not re.fullmatch(r"==[^\s]+", spec))
    if unpinned:
        raise AssertionError({"unpinned": unpinned})
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    if "pip install -r requirements.lock" not in ci or 'python-version: "3.12"' not in ci:
        raise AssertionError("CI does not enforce Python 3.12 and requirements.lock")
    print(f"P0 reproducible runtime lock: OK ({len(locked)} exact packages)")


if __name__ == "__main__":
    main()
