# Riesgos residuales

- CRÍTICO OPERATIVO: backup/restore, RPO/RTO, multiinstancia y endurance no ejecutados por indisponibilidad Docker.
- ALTO: imagen Docker no escaneada con Trivy.
- ALTO: staging local no ejecutado y staging externo no autorizado.
- ALTO: reinicio PostgreSQL y pérdida de conectividad no ensayados.
- MEDIO: staging local no certifica red, hardware ni proveedores externos.
- CONTROL: las 38 CVE de Pillow detectadas quedaron corregidas localmente con 13.0.0 y doble escaneo PASS.
- La candidata `5.8.2-rc.2` no fue publicada ni desplegada.

