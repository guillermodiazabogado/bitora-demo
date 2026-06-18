from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def section(section_id: str) -> str:
    match = re.search(
        rf'<section id="{re.escape(section_id)}" class="view">(.*?)</section>',
        HTML,
        re.S,
    )
    if not match:
        raise AssertionError(f"No existe la seccion {section_id}")
    return match.group(1)


def main() -> None:
    register = section("register")
    reception = section("reception")
    agenda = section("agenda")

    assert_true("Gestion de participantes" in register, "Inscribir no contiene la gestion completa de participantes")
    configure = section("configure")
    assert_true("Demo avanzada 1000" in configure, "Configurar Evento no muestra demo avanzada 1000")
    assert_true("Cargar demo 1000 con pico operativo" in configure, "Falta boton claro para cargar demo 1000")
    assert_true("Genera 500 participantes" not in configure, "Configurar Evento conserva texto viejo de demo 500")
    assert_true("Participantes demo para probar" not in configure, "Configurar Evento conserva cuadro de participantes demo")
    assert_true('id="demoRealPanel"' not in configure, "Configurar Evento conserva panel demoRealPanel")
    for element_id in [
        'id="searchInput"',
        'id="statusFilter"',
        'id="typeFilter"',
        'id="importForm"',
        'id="editAccreditationForm"',
        'id="accreditations"',
        'id="printFilteredBtn"',
        'id="exportLink"',
    ]:
        assert_true(element_id in register, f"Inscribir no contiene {element_id}")

    assert_true('id="reservationForm"' not in register, "Inscribir conserva el bloque viejo de reservas")
    assert_true("Gestion de inscripciones" not in register, "Inscribir conserva texto duplicado de gestion de inscripciones")

    for element_id in [
        'id="quickReceptionSearch"',
        'id="quickReceptionToken"',
        'id="quickReceptionValidate"',
        'id="quickReceptionResult"',
    ]:
        assert_true(element_id in reception, f"Recepcion no contiene {element_id}")

    for forbidden in [
        'id="accreditations"',
        'id="importForm"',
        'id="editAccreditationForm"',
        'id="statusFilter"',
        'id="typeFilter"',
        'id="printFilteredBtn"',
        'id="exportLink"',
    ]:
        assert_true(forbidden not in reception, f"Recepcion conserva listado/herramienta completa: {forbidden}")

    assert_true("reservationForm" not in agenda, "Agenda conserva gestion de inscripciones")
    assert_true("Gestion de inscripciones" not in agenda, "Agenda conserva texto de inscripciones")

    for symbol in [
        "renderAccreditationCard",
        "bindAccreditationActions",
        "loadQuickReception",
        "quickValidateReceptionToken",
        "quickReceptionSearch",
        "quickReceptionValidate",
        "Descargar QR",
        "Email",
        "Historial",
        "Reenviar portal",
    ]:
        assert_true(symbol in JS, f"Falta comportamiento JS para {symbol}")

    assert_true('compact ? quickActions : fullActions' in JS, "Recepcion no usa acciones rapidas separadas")
    assert_true("wristband-one" in JS and "certificate-one" in JS, "Inscribir perdio acciones completas")
    quick_block = JS.split("const quickActions =", 1)[1].split("const fullActions =", 1)[0]
    assert_true("wristband-one" not in quick_block and "certificate-one" not in quick_block, "Recepcion muestra acciones no operativas")
    assert_true("manual-checkin" in quick_block and "print-one" in quick_block and "WhatsApp" in quick_block, "Recepcion no mantiene acciones rapidas clave")

    assert_true('$("#reservationForm")?.addEventListener' in JS, "El listener de reservas no quedo protegido")
    assert_true("const list = $(\"#reservationsList\");" in JS, "renderReservations no quedo protegido")

    print("OK: Inscribir y Recepcion reorganizados")


if __name__ == "__main__":
    main()
