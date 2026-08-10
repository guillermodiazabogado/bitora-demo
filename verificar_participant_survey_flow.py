from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def assert_contains(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise AssertionError(f"Falta {label}: {marker}")


def main() -> None:
    server = read("server.py")
    portal = read("static/p.html")
    frontend_portal = read("frontend/p.html")

    assert_contains(server, '"/api/portal/surveys/start"', "endpoint start publico del portal")
    assert_contains(server, '"/api/portal/surveys/submit"', "endpoint submit publico del portal")
    assert_contains(server, "participant_survey_payloads", "descubrimiento de encuestas por participante")
    assert_contains(server, "portal_payload(db, token)", "resolucion por token de portal")
    assert_contains(server, "participant_id=int(portal[\"person_id\"])", "respuesta identificada por participante")
    assert_contains(server, "WHERE sa.id = ? AND sa.event_id = ? AND sa.status = 'OPEN'", "scope de asignacion por evento")
    assert_contains(server, "SURVEY_SESSION_NOT_FOUND", "bloqueo de sesion ajena")
    assert_contains(server, "survey_service().submit_response", "persistencia mediante SurveyService")

    assert_contains(portal, 'href="#encuesta"', "navegacion encuesta")
    assert_contains(portal, 'id="surveyStatus"', "panel encuesta")
    assert_contains(portal, "openSurvey", "accion abrir encuesta")
    assert_contains(portal, "submitSurvey", "accion enviar encuesta")
    assert_contains(portal, "/api/portal/surveys/start", "llamada portal start")
    assert_contains(portal, "/api/portal/surveys/submit", "llamada portal submit")
    assert_contains(portal, "Encuesta enviada. Gracias por responder.", "confirmacion UX")

    if portal != frontend_portal:
        raise AssertionError("static/p.html y frontend/p.html no estan sincronizados")

    print("OK: participant survey flow contract")


if __name__ == "__main__":
    main()
