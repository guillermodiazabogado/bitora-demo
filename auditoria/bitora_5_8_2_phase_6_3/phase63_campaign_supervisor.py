#!/usr/bin/env python3
"""Phase 6.3 supervisor adapter over the previously certified gate engine."""

from __future__ import annotations

import importlib.util
import datetime as dt
import json
import os
import pathlib


HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE.parent / "bitora_5_8_2_phase_6_2" / "phase62_campaign_supervisor.py"
SPEC = importlib.util.spec_from_file_location("bitora_phase62_supervisor", BASE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load base supervisor: {BASE}")
SUPERVISOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPERVISOR)

SUPERVISOR.HERE = HERE
SUPERVISOR.DEFAULT_CONFIG = HERE / "phase63_campaign_config.json"
_base_validate_report = SUPERVISOR.validate_report


def validate_report(report_path, expected_sha, mode, readers):
    checks = _base_validate_report(report_path, expected_sha, mode, readers)
    data = SUPERVISOR.load_json(report_path)
    profile = data["levels"][0]["access"]["sustained_qr_validation"]
    checks["postgres_access_concurrency_exact"] = (
        data.get("configuration", {}).get("postgres_access_concurrency_per_instance") == 1
    )
    if mode == "valid":
        throughput = profile.get("responses_per_second", profile.get("throughput_per_second"))
        checks["throughput_at_least_historical_baseline"] = (
            float(throughput or 0) >= 80.818
        )
    return checks


SUPERVISOR.validate_report = validate_report


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_text(path: pathlib.Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content.rstrip() + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def finalize() -> None:
    config = SUPERVISOR.load_json(HERE / "phase63_campaign_config.json")
    campaign_root = HERE / "evidence" / str(config["campaign_id"])
    checkpoint_path = campaign_root / "checkpoint.json"
    if checkpoint_path.exists():
        checkpoint = SUPERVISOR.load_json(checkpoint_path)
    else:
        checkpoint = {
            "campaign_id": config["campaign_id"], "expected_sha": config["expected_sha"],
            "status": "BLOCKED", "phase": "FINISHED", "completed": [],
            "stop_reason": "CHECKPOINT_NOT_CREATED",
        }
    rows = []
    for completed in checkpoint.get("completed", []):
        report_path = pathlib.Path(completed["report"])
        data = SUPERVISOR.load_json(report_path)
        profile = data["levels"][0]["access"]["sustained_qr_validation"]
        rows.append({
            "id": completed["id"], "status": completed["status"],
            "duration_seconds": profile.get("duration_seconds"),
            "attempted": profile.get("attempted"), "authorized": profile.get("authorized"),
            "business_rejected": profile.get("business_rejected"),
            "technical_errors": profile.get("technical_errors"),
            "responses_per_second": profile.get("responses_per_second"),
            "p95_ms": profile.get("latency_ms", {}).get("p95"),
            "p99_ms": profile.get("latency_ms", {}).get("p99"),
            "report": str(report_path), "report_sha256": completed.get("report_sha256"),
            "checks": completed.get("checks", {}),
        })
    terminal = checkpoint.get("status")
    decision = "GO-LAB" if terminal == "PASS" and len(rows) == 9 else (
        "NO-GO-LAB" if terminal == "FAIL" else "BLOCKED"
    )
    result = {
        "schema": "bitora.phase63.certification-results.v1", "generated_at": utc_now(),
        "campaign_id": config["campaign_id"], "sha": config["expected_sha"],
        "campaign_status": terminal, "decision": decision,
        "production_decision": "NO-GO", "completed_count": len(rows),
        "expected_count": 9, "stop_reason": checkpoint.get("stop_reason"), "results": rows,
    }
    SUPERVISOR.atomic_json(HERE / "RESULTADOS_CERTIFICACION.json", result)
    SUPERVISOR.atomic_json(HERE / "CHECKPOINT_FINAL.json", {**checkpoint, "finalized_at": utc_now()})
    table = ["| Prueba | Estado | Duración s | Ops | Autorizadas | Rechazos | Errores | ops/s | p95 ms | p99 ms |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        table.append(
            f"| {row['id']} | {row['status']} | {row['duration_seconds']} | {row['attempted']} | "
            f"{row['authorized']} | {row['business_rejected']} | {row['technical_errors']} | "
            f"{row['responses_per_second']} | {row['p95_ms']} | {row['p99_ms']} |"
        )
    if not rows:
        table.append("| Sin corridas completas | NOT_RUN | - | - | - | - | - | - | - | - |")
    control = f"""# BITORA 5.8.2 — Control de cierre Fase 6.3

- Campaña: `{config['campaign_id']}`
- SHA: `{config['expected_sha']}`
- Estado: **{terminal}**
- Decisión: **{decision}**
- Corridas completas: {len(rows)}/9
- Motivo de detención: `{checkpoint.get('stop_reason') or 'ninguno'}`
- Actualizado: {utc_now()}

{chr(10).join(table)}
"""
    atomic_text(HERE / "CONTROL_CIERRE_14_DIAS.md", control)
    report = f"""# BITORA 5.8.2 — Cierre técnico Fase 6.3

## Decisión

**{decision}** para laboratorio. Producción permanece **NO-GO**.

El candidato evaluado es `{config['expected_sha']}`. La campaña terminó en `{terminal}` con {len(rows)} de 9 corridas completas. No se promediaron p95 ni se convirtieron pruebas no ejecutadas en PASS.

## Cambios del candidato

- Eliminación de dos readbacks PostgreSQL no consumidos en la ruta QR.
- Gate PostgreSQL configurable, certificado con el valor conservador de una transacción QR por instancia.
- Advisory lock alineado con `organization/event/entity_id`, con fallback por acreditación, para preservar anti-passback cuando una identidad tiene más de una credencial.
- Telemetría temporal y por contenedor para separar aplicación, PostgreSQL y entorno.

## Resultado terminal

{chr(10).join(table)}

Motivo de detención: `{checkpoint.get('stop_reason') or 'ninguno'}`. Las inscripciones históricas R1/R2/R3 permanecen preservadas; producción requiere todavía staging, infraestructura, red, dispositivos físicos y simulacro operativo autorizados.
"""
    atomic_text(HERE / "INFORME_EJECUTIVO_CIERRE.md", report)


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = int(SUPERVISOR.main())
    finally:
        finalize()
    raise SystemExit(exit_code)
