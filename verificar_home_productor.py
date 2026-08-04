from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    frontend_index = read("frontend/index.html")
    static_index = read("static/index.html")
    frontend_app = read("frontend/app.js")
    static_app = read("static/app.js")
    frontend_css = read("frontend/styles.css")
    static_css = read("static/styles.css")
    server = read("server.py")

    require(frontend_index == static_index, "frontend/static index.html no estan sincronizados")
    require(frontend_app == static_app, "frontend/static app.js no estan sincronizados")
    require(frontend_css == static_css, "frontend/static styles.css no estan sincronizados")

    require('data-view="home"' in frontend_index, "Falta boton Inicio")
    require('id="home" class="view"' in frontend_index, "Falta seccion home")
    require('id="producerHomeGrid"' in frontend_index, "Falta grilla de modulos")
    require("producer-home-shell" in frontend_css, "Faltan estilos del home productor")

    require("const PRODUCER_HOME_MODULES" in frontend_app, "Falta catalogo de modulos")
    for key in [
        "dashboard",
        "register",
        "reception",
        "access",
        "attendance",
        "agenda",
        "speakers",
        "certificates",
        "surveys",
        "communications",
        "operations",
        "analytics",
    ]:
        require(f'key: "{key}"' in frontend_app, f"Falta modulo {key}")

    require('effectiveRole() === "Productor"' in frontend_app, "Home no esta limitado al rol Productor")
    require("producerModuleAllowed(module)" in frontend_app, "Falta validacion de permiso antes de abrir modulo")
    require("canSeeModule(module.permissionModule)" in frontend_app, "Falta filtro por modulo permitido")
    require("canDo(module.action)" in frontend_app, "Falta filtro por accion permitida")
    require('button.dataset.view === "home"' in frontend_app, "Falta excepcion controlada para vista home")

    require('"home"' not in server.partition("PERMISSION_MATRIX")[2].partition("PERMISSION_MODULES")[0], "No debe agregarse permiso backend nuevo para home")

    print("Home visual Productor: PASSED")


if __name__ == "__main__":
    main()
