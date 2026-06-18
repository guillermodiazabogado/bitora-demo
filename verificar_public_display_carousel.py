from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
DISPLAY = (ROOT / "frontend" / "display.html").read_text(encoding="utf-8")


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    assert_true("const CAROUSEL_PAGE_SECONDS = 20;" in DISPLAY, "El carrusel no fija 20 segundos por pantalla")
    assert_true("CAROUSEL_PAGE_SECONDS * 1000" in DISPLAY, "El temporizador no usa 20 segundos")
    assert_true("setTimeout(() =>" in DISPLAY, "El carrusel debe usar timeout propio, no intervalo acoplado al refresh")
    assert_true("let carouselSignature = \"\";" in DISPLAY, "Falta firma para no reiniciar pagina en cada refresh")
    assert_true("if (signature !== carouselSignature)" in DISPLAY, "La pagina se reinicia aunque no cambien las charlas")
    assert_true("carouselPage = 0;" in DISPLAY, "Debe reiniciar solo cuando cambia la lista o el layout")
    assert_true("Math.min(refreshSeconds" not in DISPLAY, "El carrusel sigue limitado por refreshSeconds")
    assert_true("setInterval(() => {\n        const pages" not in DISPLAY, "Quedo el intervalo viejo de rotacion")
    print("OK: pantalla publica rota cada 20 segundos por pagina")


if __name__ == "__main__":
    main()
