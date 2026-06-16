from __future__ import annotations

from qa2_utils import (
    Harness,
    QA2Error,
    accreditation_id_for,
    create_activity,
    create_event,
    first_space_id,
    register,
    request,
)


def must_forbid(result, label: str) -> None:
    if result[0] != 403:
        raise QA2Error(f"{label}: no fue bloqueado, status={result[0]} body={result[1]}")


def main() -> None:
    h = Harness("qa2-security-")
    try:
        h.start()
        event_id = create_event(h.base, "QA2 Seguridad")
        space_id = first_space_id(h.base, event_id)
        activity_id = create_activity(h.base, event_id, space_id, "Seguridad", capacity=10)
        reg1 = register(h.base, event_id, 1, "sec")
        reg2 = register(h.base, event_id, 2, "sec")
        acc_id = accreditation_id_for(reg1["token"])

        must_forbid(request(h.base, "POST", "/api/events", {"actor": "Acceso", "name": "No", "status": "published"}), "Acceso crea evento")
        bags = request(h.base, "GET", f"/api/capacity-bags?event_id={event_id}&activity_id={activity_id}")[1]
        must_forbid(request(h.base, "POST", "/api/capacity-bags", {"actor": "Acceso", "id": bags[0]["id"], "assigned_capacity": 99}), "Acceso modifica cupos")
        must_forbid(request(h.base, "POST", "/api/communications/send", {"actor": "Acceso", "event_id": event_id, "audience": "all", "channel": "email", "content": "x"}), "Acceso envia comunicaciones")
        must_forbid(request(h.base, "POST", "/api/prepare-event", {"actor": "Recepcion", "name": "No"}), "Recepcion prepara evento")
        must_forbid(request(h.base, "POST", "/api/accreditations/update", {"actor": "Visualizador", "id": acc_id, "first_name": "No"}), "Visualizador edita")

        public = request(h.base, "GET", f"/api/public-display?event_id={event_id}")[1]
        public_text = str(public).lower()
        for secret in ("sec.1@example.test", "5491100", "dni"):
            if secret in public_text:
                raise QA2Error("pantalla publica expone datos sensibles")

        control = request(h.base, "GET", f"/api/reports/visual-summary?event_id={event_id}")[1]
        control_text = str(control).lower()
        for secret in ("sec.1@example.test", "5491100", "50000001"):
            if secret in control_text:
                raise QA2Error("sala de control expone datos sensibles")

        qr_status, qr_svg = request(h.base, "GET", f"/api/qr.svg?token={reg1['token']}", parse_json=False)
        if qr_status != 200:
            raise QA2Error("QR no disponible")
        qr_text = qr_svg.decode("utf-8", "ignore") if isinstance(qr_svg, bytes) else str(qr_svg)
        for secret in ("sec.1@example.test", "Nombre1", "Apellido1", "50000001"):
            if secret in qr_text:
                raise QA2Error("QR contiene datos personales")

        own = request(h.base, "GET", f"/api/portal?token={reg1['token']}")
        other = request(h.base, "GET", f"/api/portal?token={reg2['token']}")
        if own[0] != 200 or other[0] != 200:
            raise QA2Error("portal no respondio")
        if "sec.2@example.test" in str(own[1]) or "sec.1@example.test" in str(other[1]):
            raise QA2Error("portal permite ver datos de otro participante")

        print("OK: seguridad basica y permisos")
    finally:
        h.cleanup()


if __name__ == "__main__":
    main()
