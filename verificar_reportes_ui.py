from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    require("control-room-settings" in INDEX, "Falta configuracion ordenada de Sala de Control")
    require("control-room-modes" in INDEX, "Faltan modos de Sala de Control")
    require("Bloques visibles" in INDEX, "Falta selector de bloques")
    require(".visual-block-picker input" in CSS and "width: 16px" in CSS, "Checkboxes de reportes conservan dimensiones incorrectas")
    require("report-download-grid" in INDEX and ".report-download-grid" in CSS, "Falta grilla de reportes")

    report_ids = {
        "reportsAccreditationsLink": "/api/export.csv",
        "reportsReservationsLink": "/api/reservations.csv",
        "reportsAttendancesLink": "/api/attendances.csv",
        "reportsEligibilityLink": "/api/certificate-eligibility.csv",
        "reportsExportCaptationLink": "/api/captation.csv",
        "reportsExportJsonLink": "/api/export.json",
    }
    for report_id, endpoint in report_ids.items():
        require(f'id="{report_id}"' in INDEX, f"Falta tarjeta {report_id}")
        require(f'setHref("#{report_id}"' in APP and endpoint in APP, f"{report_id} no esta conectado")

    require((ROOT / "static" / "index.html").read_text(encoding="utf-8") == INDEX, "index frontend/static desincronizado")
    require((ROOT / "static" / "app.js").read_text(encoding="utf-8") == APP, "app frontend/static desincronizado")
    require((ROOT / "static" / "styles.css").read_text(encoding="utf-8") == CSS, "styles frontend/static desincronizado")
    print("OK reportes_ui")


if __name__ == "__main__":
    main()
