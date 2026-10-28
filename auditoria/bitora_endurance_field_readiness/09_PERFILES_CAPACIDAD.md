# Perfiles de capacidad

Los perfiles A (500 participantes, 2 puertas, 4 dispositivos, 2 operadores), B (3.000, 6, 12, 6) y C (10.000, 12, 24, 12) están definidos en `scripts/operational_endurance_profiles.py`. Son escenarios sintéticos, no capacidad demostrada.

El smoke local del generador y su telemetría aprobó, registrando CPU, RSS, heap, tamaño de base, conexiones, throughput, integridad y eventos persistidos. Su backend SQLite es solamente un pre-gate funcional del runner; no sustituye la endurance integrada HTTP + PostgreSQL + dos instancias.

Las etapas de 15 minutos, 60 minutos y 6 horas reales permanecen **NOT RUN**. El perfil C no se ejecutará si el entorno autorizado no tiene recursos suficientes.
