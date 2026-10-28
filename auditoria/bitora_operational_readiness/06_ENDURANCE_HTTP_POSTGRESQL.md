# Endurance HTTP + PostgreSQL

Estado: **NOT RUN / BLOCKED**.

La prueba integrada está incorporada al harness multiinstancia y alterna ENTRY/EXIT HTTP reales entre dos aplicaciones con PostgreSQL compartido, midiendo intentos, éxitos, errores y latencias p50/p95/p99. Duración inicial: 10 segundos; extensión configurable.

No comenzó porque `docker info` no respondió. La endurance SQLite histórica y el smoke de la RC anterior no sustituyen esta prueba.

