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
    attendance_page = read("frontend/attendance-closure.html")
    speakers_page = read("frontend/speakers-v4.html")
    static_speakers_page = read("static/speakers-v4.html")
    certificates_page = read("frontend/certificates-v4.html")
    static_certificates_page = read("static/certificates-v4.html")
    surveys_page = read("frontend/surveys-v4.html")
    static_surveys_page = read("static/surveys-v4.html")
    analytics_page = read("frontend/analytics-v4.html")
    operations_page = read("static/operations-center-v4.html")
    server = read("server.py")

    require(frontend_index == static_index, "frontend/static index.html no estan sincronizados")
    require(frontend_app == static_app, "frontend/static app.js no estan sincronizados")
    require(frontend_css == static_css, "frontend/static styles.css no estan sincronizados")

    require('data-view="home"' in frontend_index, "Falta boton Inicio")
    require('id="producerHomeReturnBtn"' in frontend_index, "Falta boton Volver al Home en SPA")
    require('data-view-target="home"' in frontend_index, "Volver al Home debe usar navegacion autorizada de la SPA")
    require('id="home" class="view"' in frontend_index, "Falta seccion home")
    require('id="producerHomeGrid"' in frontend_index, "Falta grilla de modulos")
    require("producer-home-shell" in frontend_css, "Faltan estilos del home productor")
    require("producer-home-return" in frontend_css, "Faltan estilos del retorno al Home")

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
    require("updateProducerHomeReturn" in frontend_app, "Falta control de visibilidad del boton Volver al Home")
    require('producerHomeAllowed() && name !== "home"' in frontend_app, "Volver al Home debe limitarse a Productor con Home disponible")
    require('button.dataset.view === "home"' in frontend_app, "Falta excepcion controlada para vista home")

    separated_pages = {
        "attendance": attendance_page,
        "speakers": speakers_page,
        "certificates": certificates_page,
        "surveys": surveys_page,
        "operations": operations_page,
        "analytics": analytics_page,
    }
    for name, content in separated_pages.items():
        require("producerHomeLink" in content, f"Falta enlace Volver al Home en {name}")
        require("#home" in content, f"El retorno de {name} no apunta al Home")
        require("event_id" in content, f"El retorno de {name} no conserva event_id")

    require(speakers_page == static_speakers_page, "frontend/static speakers-v4.html no estan sincronizados")
    require(certificates_page == static_certificates_page, "frontend/static certificates-v4.html no estan sincronizados")
    require(surveys_page == static_surveys_page, "frontend/static surveys-v4.html no estan sincronizados")

    require('"home"' not in server.partition("PERMISSION_MATRIX")[2].partition("PERMISSION_MODULES")[0], "No debe agregarse permiso backend nuevo para home")

    print("Home visual Productor: PASSED")


if __name__ == "__main__":
    main()
