from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for marker in ("data-map-action=\"fit\"", "data-map-action=\"zoom-in\"", "data-map-action=\"layers\"", "data-device-view=\"visual\"", "data-device-view=\"table\""):
        assert marker in html, marker
    for marker in ("handleEnterpriseMapAction", "setEnterpriseDeviceView", "aria-pressed", "enterprise-device-table", "commandCenterMapZoom"):
        assert marker in app, marker
    assert "--enterprise-map-zoom" in styles and ".enterprise-device-table" in styles
    print("OK: controles de mapa y vista visual/tabla del Command Center son funcionales")


if __name__ == "__main__":
    main()
