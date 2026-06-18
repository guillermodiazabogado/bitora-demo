from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    require('id="backupLink" class="button action-backup"' in INDEX, "Backup debe verse como boton destacado")
    require('class="action-config" data-view-target="configure"' in INDEX, "Configurar Evento debe verse como boton destacado")
    require('class="template-card"' in INDEX, "Plantillas y Agenda debe usar tarjetas")
    require("Crear desde evento" in INDEX, "Debe existir tarjeta Crear desde evento")
    require("Exportar planillas" in INDEX, "Debe existir tarjeta Exportar planillas")
    require("Importar estructura" in INDEX, "Debe existir tarjeta Importar estructura")
    require("Importar agenda" in INDEX, "Debe existir tarjeta Importar agenda")
    require(".template-actions" in CSS and "grid-template-columns: repeat(3" in CSS, "Plantillas debe estar ordenado en grilla")
    require(".action-backup" in CSS and ".action-config" in CSS, "Faltan estilos de botones del panel")
    require("Participantes demo para probar" not in INDEX, "El panel demo no debe mostrarse en Configurar Evento")
    print("OK configuracion_evento_ui")


if __name__ == "__main__":
    main()
