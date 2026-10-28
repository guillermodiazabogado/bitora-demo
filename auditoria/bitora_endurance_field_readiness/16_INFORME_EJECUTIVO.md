# Informe ejecutivo

El SHA remoto `ba97404fad89ee166084944ad55785f1aa72ad8f` contiene la corrección fail-fast de readiness, endurecimiento del cliente Edge, perfiles y runner de endurance, observabilidad mínima, workflow progresivo y protocolos de campo. La revisión independiente y el secret scan aprobaron.

Los runs remotos `40735837313` y `40738606063` demostraron HTTP + PostgreSQL 16 + dos instancias durante 15 y 60 minutos reales. La etapa de 60 minutos procesó 321.488/321.488 operaciones sin fallos técnicos, con p95 13,056 ms y p99 14,016 ms. Backup/restore, recuperación, Docker, dependencias y escaneo de imagen aprobaron.

La endurance de seis horas no puede ejecutarse honestamente en el recurso disponible: no hay runner self-hosted y el límite del runner hospedado es seis horas, sin margen para preparar o cerrar evidencia. Permanece BLOCKED, no PASS.

El commit final funcional `a402f8e48db842454738561374e18efa7454bf8e` agregó el disparo explícito de CI y aprobó el Run `40749664713`, incluyendo PostgreSQL, SBOM, Docker build y healthcheck. La rama auxiliar `release/5.8.2-endurance-field-ci` solo se utilizó para activar el workflow existente; no hubo merge, release ni despliegue.

Decisiones vigentes:

- Software: GO.
- Laboratorio Nivel 2: PASS para 15/60 minutos; BLOCKED para seis horas.
- Simulacro físico: NO-GO hasta endurance, red y dispositivos reales.
- Producción: NO-GO.
