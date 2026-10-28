from __future__ import annotations
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FILES=("enterprise-vehicles.html","enterprise-vehicles.css","enterprise-vehicles.js")
def require(text,pattern,label):
    if not re.search(pattern,text,re.MULTILINE): raise AssertionError(f"Falta contrato UI: {label}")
def main():
    for name in FILES:
        for folder in ("static","frontend"): assert (ROOT/folder/name).is_file(),f"Falta {folder}/{name}"
    compact=lambda value:re.sub(r"\s+","",value)
    assert compact((ROOT/"static"/FILES[1]).read_text(encoding="utf-8"))==compact((ROOT/"frontend"/FILES[1]).read_text(encoding="utf-8")),"CSS divergente"
    for folder in ("static","frontend"):
        html=(ROOT/folder/FILES[0]).read_text(encoding="utf-8");js=(ROOT/folder/FILES[2]).read_text(encoding="utf-8")
        for item in ("scopeForm","organizationId","eventId","dashboardLoading","dashboardEmpty","dashboardError","metrics","accessForm","plate","idempotencyKey","accessResult"): require(html,rf'id="{item}"',f"{folder}:{item}")
        require(html,r'aria-live="polite"',f"{folder}:aria-live");require(js,r'fetch\("/api/auth/me"',f"{folder}:auth me");require(js,r'X-CSRF-Token',f"{folder}:csrf header")
        require(js,r'/api/v5/organizations/\$\{state\.scope\.organizationId\}/events/\$\{state\.scope\.eventId\}/vehicles',f"{folder}:scope route");require(js,r'route\("/dashboard"\)',f"{folder}:dashboard");require(js,r'route\("/access"\)',f"{folder}:access")
        require(js,r'ENTRY',f"{folder}:entry");require(js,r'EXIT',f"{folder}:exit");require(js,r'ANTI_PASSBACK',f"{folder}:anti-passback");require(js,r'NO_ACTIVE_SLOT',f"{folder}:slot");require(js,r'idempotency',f"{folder}:idempotency");require(js,r'textContent',f"{folder}:safe render")
        assert not any(word in (html+js).lower() for word in ("mock","fixture","example.test")),f"Datos ficticios en {folder}"
    print("OK: Enterprise Vehicles UI scoped, CSRF, idempotencia y estados operativos")
if __name__=="__main__":main()
