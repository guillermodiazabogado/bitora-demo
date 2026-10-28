from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOCKERFILES = (ROOT / "Dockerfile", ROOT / "deployment" / "Dockerfile.staging")


def validate(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    if not re.search(r"(?im)^COPY\s+(?:--\S+\s+)*requirements\.lock\s+", text):
        errors.append("no copia requirements.lock")
    if not re.search(r"(?im)^RUN\s+pip\s+install\b[^\n]*-r\s+requirements\.lock\b", text):
        errors.append("no instala requirements.lock")
    if re.search(r"(?im)^\s*(?:COPY|RUN)\b[^\n]*requirements\.txt\b", text):
        errors.append("usa requirements.txt con rangos no bloqueados")

    user_matches = re.findall(r"(?im)^USER\s+([^\s#]+)", text)
    if not user_matches:
        errors.append("no declara usuario de runtime")
    elif user_matches[-1].lower() in {"root", "0"}:
        errors.append("el usuario final es root")
    if "--uid 10001 bitora" not in text or not re.search(r"(?im)^USER\s+bitora\s*$", text):
        errors.append("no usa la identidad bitora UID 10001")

    health = re.search(r"(?ims)^HEALTHCHECK\b.*?(?=^CMD\s*\[|\Z)", text)
    if not health:
        errors.append("no declara HEALTHCHECK")
    elif "/ready" not in health.group(0):
        errors.append("HEALTHCHECK no usa readiness")

    return errors


def main() -> None:
    findings = {str(path.relative_to(ROOT)): validate(path) for path in DOCKERFILES}
    findings = {path: errors for path, errors in findings.items() if errors}
    if findings:
        for path, errors in findings.items():
            for error in errors:
                print(f"FAIL {path}: {error}")
        raise SystemExit(1)
    print("OK - Dockerfiles reproducibles, no-root y con readiness")


if __name__ == "__main__":
    main()
