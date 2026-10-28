from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FILES = ("enterprise-leads.html", "enterprise-leads.css", "enterprise-leads.js")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(text: str, pattern: str, label: str) -> None:
    if not re.search(pattern, text, re.MULTILINE):
        raise AssertionError(f"Falta contrato UI: {label}")


def main() -> None:
    for name in FILES:
        static = ROOT / "static" / name
        frontend = ROOT / "frontend" / name
        assert static.is_file() and frontend.is_file(), f"Falta replica {name}"
        if name.endswith(".css"):
            assert digest(static) == digest(frontend), f"Replica divergente: {name}"
        elif name.endswith(".html"):
            normalize = lambda value: re.sub(r"\s+", " ", value).replace("> <", "><").strip()
            assert normalize(static.read_text(encoding="utf-8")) == normalize(frontend.read_text(encoding="utf-8")), f"Replica HTML divergente: {name}"

    html = (ROOT / "static" / FILES[0]).read_text(encoding="utf-8")
    script = (ROOT / "static" / FILES[2]).read_text(encoding="utf-8")
    for root_name in ("static", "frontend"):
        candidate_html = (ROOT / root_name / FILES[0]).read_text(encoding="utf-8")
        candidate_script = (ROOT / root_name / FILES[2]).read_text(encoding="utf-8")
        for element_id in ("scopeForm", "organizationId", "eventId", "companyId", "status", "captureForm", "captureIdempotency", "leadsLoading", "leadsEmpty", "leadsError", "leadsTable", "exportForm"):
            require(candidate_html, rf'id="{element_id}"', f"{root_name}:{element_id}")
        require(candidate_html, r'aria-live="polite"', f"{root_name}:estado accesible")
        require(candidate_script, r"/api/v5/organizations/\$\{organizationId\}/events/\$\{eventId\}", f"{root_name}:scope organization/event")
        require(candidate_script, r"/companies/\$\{state\.scope\.companyId\}/leads", f"{root_name}:scope company/listado")
        require(candidate_script, r'route\("/leads/captures"\)', f"{root_name}:captura V5")
        require(candidate_script, r"/leads/export", f"{root_name}:export V5")
        require(candidate_script, r"idempotency_key", f"{root_name}:idempotencia")
        require(candidate_script, r"consent_id", f"{root_name}:consentimiento")
        require(candidate_script, r"textContent", f"{root_name}:render seguro")
    forbidden = ("mock", "fixture", "ana.demo@example.test", "luis.demo@example.test")
    lowered = (html + script).lower()
    assert not any(item in lowered for item in forbidden), "La UI contiene datos ficticios o mocks"
    print("OK: Enterprise Leads UI conectada, scoped, consentida, idempotente y replicada")


if __name__ == "__main__":
    main()
