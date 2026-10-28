from __future__ import annotations
import hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent;FILES=("enterprise-vouchers.html","enterprise-vouchers.css","enterprise-vouchers.js")
def require(text,pattern,label):
    if not re.search(pattern,text,re.MULTILINE):raise AssertionError(f"Falta contrato UI: {label}")
def main():
    for name in FILES:
        a=ROOT/"static"/name;b=ROOT/"frontend"/name
        assert a.is_file() and b.is_file(),f"Falta réplica {name}"
        left=a.read_text(encoding="utf-8");right=b.read_text(encoding="utf-8")
        if name.endswith(".css"):
            left=re.sub(r"\s+","",left);right=re.sub(r"\s+","",right)
        assert hashlib.sha256(left.encode()).hexdigest()==hashlib.sha256(right.encode()).hexdigest(),f"Réplica no exacta: {name}"
    html=(ROOT/"static"/FILES[0]).read_text(encoding="utf-8");js=(ROOT/"static"/FILES[2]).read_text(encoding="utf-8")
    for item in ("scopeForm","organizationId","eventId","status","reportLoading","reportEmpty","reportError","participantForm","participantEmpty","assignForm","assignKey","consumeForm","consumeKey","consumeResult"):require(html,rf'id="{item}"',item)
    require(html, r'name="idempotency_key"', "idempotency")
    for pattern,label in ((r'fetch\("/api/auth/me"',"auth"),(r'X-CSRF-Token',"csrf"),(r'/api/organizations/\$\{state\.scope\.organizationId\}/events/\$\{state\.scope\.eventId\}/vouchers',"scope"),(r'/participants/current',"participant"),(r'/report',"report"),(r'/assignments',"assign"),(r'/consumptions',"consume"),(r'duplicate',"duplicate"),(r'EXHAUSTED',"agotado"),(r'denegad',"denegado"),(r'textContent',"render seguro")):require(js,pattern,label)
    assert not any(word in (html+js).lower() for word in ("mock","fixture","example.test")),"Datos ficticios detectados"
    print("OK: Enterprise Vouchers UI exacta, scoped, CSRF e idempotente")
if __name__=="__main__":main()
