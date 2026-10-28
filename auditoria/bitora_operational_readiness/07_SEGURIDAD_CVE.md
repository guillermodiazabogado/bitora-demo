# Seguridad y CVE

## Dependencias

- pip-audit 2.10.1 sobre `requirements.lock`: 38 vulnerabilidades en Pillow 12.3.0, varias con corrección en 13.0.0.
- Corrección: `pillow==13.0.0`.
- Reejecución pip-audit: **PASS, sin vulnerabilidades conocidas**.
- Reejecución OSV querybatch: **PASS, sin findings**.
- SBOM CycloneDX regenerado: 18 componentes.

## Regresiones

Secret scan, sesiones persistentes y revocación por contraseña/estado/rol: PASS.

## Imagen

Trivy 0.67.2 quedó integrado en `scripts/operational_cve_scan.py`, pero su ejecución está **BLOCKED** porque Docker no responde. No se afirma que la imagen esté libre de CVE.

