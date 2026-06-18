from pathlib import Path


def main() -> None:
    html = (Path("frontend") / "noc.html").read_text(encoding="utf-8")
    css = (Path("frontend") / "styles.css").read_text(encoding="utf-8")
    js = (Path("frontend") / "noc.js").read_text(encoding="utf-8")
    for panel in ("nocGeneral", "nocAccess", "nocAccreditations", "nocRooms", "nocAlerts", "nocRejections", "nocFlow", "nocTerminals", "nocCommunications", "nocInfrastructure"):
        assert f'id="{panel}"' in html
    assert "overflow: hidden" in css and "height: 100vh" in css
    assert "/api/diagnostics/status" in js and "occupancy_by_room" in js
    print("OK: V6.6 NOC fijo, sin scroll, paneles operativos e infraestructura")


if __name__ == "__main__":
    main()
