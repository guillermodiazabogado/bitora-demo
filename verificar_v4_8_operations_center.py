import os
import tempfile
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "v4_8_operations.sqlite3")
os.environ["BITORA_OPERATIONS_CENTER_V4_ENABLED"] = "true"
os.environ["BITORA_STORAGE_PATH"] = str(root / "storage")
os.environ["QR_REQUIRE_LOGIN"] = ""

import server  # noqa: E402


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    server.init_db()
    now = server.now_iso()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        cur = db.execute("INSERT INTO organizations (public_id,name,legal_name,trade_name,status,plan,created_at,updated_at) VALUES ('ops-v48','Ops Alfa','Ops Alfa','Ops Alfa','active','standard',?,?)", (now, now))
        org_id = int(cur.lastrowid)
        event = db.execute("INSERT INTO events (organization_id,name,starts_at,ends_at,status,created_at) VALUES (?,?,? ,?,'draft',?)", (org_id, "Evento Operations", "2026-12-02T09:00:00+00:00", "2026-12-02T18:00:00+00:00", now))
        event_id = int(event.lastrowid)
        space = db.execute("INSERT INTO spaces (event_id,name,capacity,created_at) VALUES (?,?,100,?)", (event_id, "Sala", now))
        db.execute("INSERT INTO activities (event_id,space_id,title,description,speaker,activity_type,starts_at,ends_at,capacity,status,created_at) VALUES (?,?,?,'','','talk',?,?,100,'active',?)", (event_id, int(space.lastrowid), "Apertura", "2026-12-02T10:00:00+00:00", "2026-12-02T11:00:00+00:00", now))
        db.execute("INSERT INTO audit_logs (event_id,actor,action,entity_type,entity_id,payload,created_at) VALUES (?,?,?,?,?,?,?)", (event_id, "tester", "ops.seed", "event", event_id, "{}", now))
        db.execute("COMMIT")
    service = server.operations_center_service()
    with server.connect() as db:
        center = service.center(db, organization_id=org_id, event_id=event_id, actor="tester")
        check(center["ok"] and center["event"]["organization_id"] == org_id, "agregacion invalida")
        check(center["metrics"]["activities"]["value"] == 1, "metrica de actividades incorrecta")
        check(center["readiness"]["items"], "readiness vacio")
        first_alerts = service.alerts(db, organization_id=org_id, event_id=event_id)
        service.center(db, organization_id=org_id, event_id=event_id, actor="tester")
        second_alerts = service.alerts(db, organization_id=org_id, event_id=event_id)
        check(len(second_alerts) == len(first_alerts), "alerta duplicada")
        incident = service.create_incident(db, organization_id=org_id, event_id=event_id, actor="tester", data={"title": "Puerta", "severity": "HIGH"})
        task = service.create_task(db, organization_id=org_id, event_id=event_id, actor="tester", data={"title": "Asignar operador", "priority": "HIGH", "incident_id": incident["item"]["id"]})
        check(service.update_incident(db, organization_id=org_id, event_id=event_id, incident_id=incident["item"]["id"], actor="tester", data={"status": "RESOLVED"})["item"]["status"] == "RESOLVED", "incidente no actualizable")
        check(service.update_task(db, organization_id=org_id, event_id=event_id, task_id=task["item"]["id"], actor="tester", data={"status": "COMPLETED"})["item"]["status"] == "COMPLETED", "tarea no actualizable")
        try:
            service.metrics(db, organization_id=org_id + 1, event_id=event_id)
            raise AssertionError("cross-tenant permitido")
        except server.OperationsCenterError:
            pass
    print("V4.8 operations center foundation: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
