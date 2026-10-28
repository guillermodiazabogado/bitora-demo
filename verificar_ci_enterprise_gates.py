from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

REQUIRED_PUSH_BRANCHES = ("main", "develop/v4", "deployment/v4-online", "release/**")
REQUIRED_GATES = (
    "python verificar_p0_lead_company_scope.py",
    "python verificar_docker_reproducible.py",
    "python verificar_enterprise_leads_ui.py",
    "python -m tools.edge_client.verify_reference_client",
)


def push_branches(text: str) -> set[str]:
    match = re.search(
        r"(?ms)^\s{2}push:\s*\n\s{4}branches:\s*\n(?P<body>(?:\s{6}-[^\n]+\n)+)",
        text,
    )
    if not match:
        return set()
    result = set()
    for raw in re.findall(r"(?m)^\s{6}-\s*(.+?)\s*$", match.group("body")):
        result.add(raw.strip().strip('"').strip("'"))
    return result


def main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    errors: list[str] = []

    branches = push_branches(text)
    for branch in REQUIRED_PUSH_BRANCHES:
        if branch not in branches:
            errors.append(f"falta trigger push para {branch}")

    if not re.search(r"(?m)^\s{2}pull_request:\s*$", text):
        errors.append("falta trigger pull_request")

    for gate in REQUIRED_GATES:
        occurrences = text.count(gate)
        if occurrences != 1:
            errors.append(f"gate esperado exactamente una vez ({occurrences}): {gate}")

    # All requested commands must remain inside the existing regression step,
    # before the independent secret-scan step.
    regression_start = text.find("- name: Critical regression gates")
    secret_scan_start = text.find("- name: Secret scan")
    if regression_start < 0 or secret_scan_start <= regression_start:
        errors.append("estructura de gates/secret scan invalida")
    else:
        regression = text[regression_start:secret_scan_start]
        for gate in REQUIRED_GATES:
            if gate not in regression:
                errors.append(f"gate fuera del bloque Critical regression gates: {gate}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        raise SystemExit(1)
    print("OK - CI cubre main/release y gates enterprise requeridos")


if __name__ == "__main__":
    main()
