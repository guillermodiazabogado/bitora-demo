from __future__ import annotations

from copy import deepcopy


VERTICALS = {
    "conference": {
        "key": "conference",
        "name": "Conference",
        "description": "Congresos, jornadas, ferias, exposiciones y capacitaciones.",
        "status": "active",
        "modules": {
            "dashboard": True,
            "registration": True,
            "reception": True,
            "agenda": True,
            "activities": True,
            "capacity": True,
            "waitlist": True,
            "attendance": True,
            "certificates": True,
            "access": True,
            "communications": True,
            "reports": True,
            "data_visualization": True,
            "noc": True,
            "simulator": True,
            "ticketing": False,
            "seats": False,
            "functions": False,
            "pricing": False,
        },
        "permissions_namespace": "conference",
        "message_namespace": "conference",
    },
    "ticketing": {
        "key": "ticketing",
        "name": "Ticketing",
        "description": "Teatro, espectaculos, recitales, funciones y eventos con entradas.",
        "status": "building",
        "modules": {
            "dashboard": True,
            "registration": False,
            "reception": False,
            "agenda": False,
            "activities": False,
            "capacity": False,
            "waitlist": False,
            "attendance": False,
            "certificates": False,
            "access": False,
            "communications": True,
            "reports": True,
            "data_visualization": True,
            "noc": True,
            "simulator": True,
            "ticketing": True,
            "seats": False,
            "functions": False,
            "pricing": False,
        },
        "permissions_namespace": "ticketing",
        "message_namespace": "ticketing",
    },
}


def normalize_project_type(value: object) -> str:
    key = str(value or "conference").strip().lower()
    return key if key in VERTICALS else "conference"


def vertical_config(value: object) -> dict:
    return deepcopy(VERTICALS[normalize_project_type(value)])


def registered_verticals() -> list[dict]:
    return [vertical_config(key) for key in ("conference", "ticketing")]
