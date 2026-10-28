from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def locked_packages() -> list[tuple[str, str]]:
    packages = []
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", line.strip())
        if match:
            packages.append((match.group(1), match.group(2)))
    return packages


def query_osv(packages: list[tuple[str, str]]) -> list[dict]:
    payload = {"queries": [{"package": {"ecosystem": "PyPI", "name": name}, "version": version} for name, version in packages]}
    request = urllib.request.Request(
        "https://api.osv.dev/v1/querybatch",
        json.dumps(payload).encode("utf-8"),
        {"Content-Type": "application/json", "User-Agent": "BITORA-operational-readiness"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))["results"]


def main() -> int:
    parser = argparse.ArgumentParser(description="OSV + Trivy operational security gate")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--image", default="", help="Optional already-built image name")
    args = parser.parse_args()
    packages = locked_packages()
    report: dict = {"ok": False, "packages": len(packages), "dependency_scan": {}, "image_scan": {"state": "NOT_RUN"}}
    try:
        results = query_osv(packages)
        findings = []
        for (name, version), result in zip(packages, results):
            for vulnerability in result.get("vulns", []):
                findings.append({"package": name, "version": version, "id": vulnerability.get("id"), "aliases": vulnerability.get("aliases", [])})
        report["dependency_scan"] = {"state": "PASS" if not findings else "FAIL", "source": "OSV querybatch", "findings": findings}
    except Exception as exc:
        report["dependency_scan"] = {"state": "BLOCKED", "error": type(exc).__name__}
    if args.image:
        try:
            completed = subprocess.run(
                ["docker", "run", "--rm", "aquasec/trivy:0.67.2", "image", "--quiet", "--format", "json", "--severity", "HIGH,CRITICAL", args.image],
                cwd=ROOT, text=True, capture_output=True, timeout=900,
            )
            if completed.returncode not in {0, 1}:
                raise RuntimeError("TRIVY_EXECUTION_FAILED")
            payload = json.loads(completed.stdout or "{}")
            vulnerabilities = [v for result in payload.get("Results", []) for v in (result.get("Vulnerabilities") or [])]
            report["image_scan"] = {"state": "PASS" if not vulnerabilities else "FAIL", "scanner": "Trivy 0.67.2", "high_critical": len(vulnerabilities)}
        except Exception as exc:
            report["image_scan"] = {"state": "BLOCKED", "scanner": "Trivy 0.67.2", "error": type(exc).__name__}
    report["ok"] = report["dependency_scan"].get("state") == "PASS" and report["image_scan"].get("state") in {"PASS", "NOT_RUN"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

