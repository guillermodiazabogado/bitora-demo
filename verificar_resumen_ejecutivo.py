from pathlib import Path

from pypdf import PdfReader

import server


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output" / "pdf"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with server.connect() as db:
        row = db.execute("SELECT id FROM events ORDER BY id DESC LIMIT 1").fetchone()
        require(row, "No existe un evento para generar el informe")
        event_id = int(row["id"])
        data = server.executive_report_data(db, event_id)

    require(data and data["event"], "No se pudo obtener datos ejecutivos")
    body = server.executive_report_pdf_bytes(data)
    require(body.startswith(b"%PDF"), "La salida no es un PDF")
    require(len(body) > 5000, "El PDF generado esta vacio o incompleto")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "bitora-resumen-ejecutivo-prueba.pdf"
    target.write_bytes(body)
    reader = PdfReader(target)
    require(len(reader.pages) >= 3, "El resumen ejecutivo debe tener al menos tres paginas")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for expected in (
        "RESUMEN EJECUTIVO",
        "Lectura ejecutiva",
        "Ocupacion y actividades",
        "Accesos, rechazos y captacion",
    ):
        require(expected in text, f"Falta seccion: {expected}")

    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    require('id="reportsExecutivePdfLink"' in index, "Falta boton de resumen ejecutivo")
    require("/api/reports/executive.pdf" in app, "El boton PDF no esta conectado")
    print(f"OK resumen_ejecutivo event_id={event_id} pages={len(reader.pages)} bytes={len(body)} path={target}")


if __name__ == "__main__":
    main()
