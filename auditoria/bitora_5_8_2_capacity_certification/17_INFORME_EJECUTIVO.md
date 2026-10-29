# Informe ejecutivo

La fase corrigió un defecto real: las inscripciones creadas después de activar el motor V5 no recibían credencial enterprise y el acceso devolvía `UNKNOWN_CREDENTIAL`. La regresión y cuatro controles de acceso pasaron localmente.

Sobre el SHA de código `3f3afde96558414b4af23c1c100a77f3d90a0111`, BITORA sostuvo en tres repeticiones frescas de 15 segundos:

- 1 instancia: ≥27,817 inscripciones completas/s con 25 workers.
- 2 instancias: ≥41,773 inscripciones/s y ≥87,558 decisiones QR HTTP/s con 24 lectores virtuales.
- 4 instancias: ≥52,412 inscripciones/s y ≥118,544 decisiones QR HTTP/s con 24 lectores virtuales.
- 4×100 alcanzó hasta 79,076 inscripciones/s, pero no se certifica por incumplimiento variable de latencia.

No hubo errores técnicos, pérdidas, duplicados, deadlocks, OOM ni reinicios inesperados en los puntos frescos. El primer límite fue la serialización/transacción por proceso y la presión de pools PostgreSQL; agregar instancias mejoró el rendimiento de manera sublineal.

Las cifras QR incluyen mayormente rechazos anti-passback; no son accesos autorizados/s. Estas cifras certifican ráfaga corta repetible, no por sí solas carga sostenida. El máximo de registros observado fue 7.941, no 25.000/50.000. No se certificaron sesiones autenticadas masivas, Edge HTTP, lectores físicos ni red de evento. La decisión es GO de laboratorio dentro de los límites medidos y NO-GO para producción.

Sobre `6ba0aebb92fe0a7a21ede00eb2b515d277fe5eb1`, la etapa sostenida agregó tres corridas de inscripción 2×25 durante 120 segundos: mínimo 38,045 altas/s, p95 máximo 1,35 s y cero fallos. En QR, 24 y 12 lectores no cumplieron p95 ≤500 ms; 8 lectores sí (76,983 decisiones/s, p95 163 ms) en una corrida. La recomendación sostenida queda en 2 instancias/25 workers y, provisionalmente, hasta 8 lectores virtuales hasta repetir o corregir el cuello de botella.
