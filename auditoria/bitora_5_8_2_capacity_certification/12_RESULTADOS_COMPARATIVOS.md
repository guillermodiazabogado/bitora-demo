# Resultados comparativos

Fuente procesable: `evidencia/capacity-certified-summary.csv`. Cada punto certificado tiene tres ejecuciones frescas.

```mermaid
xychart-beta
  title "Inscripciones/s con 50 workers"
  x-axis "Instancias" [1, 2, 4]
  y-axis "Inscripciones/s" 0 --> 60
  line [28.78, 41.83, 52.55]
```

```mermaid
xychart-beta
  title "QR/s promedio con 24 lectores virtuales"
  x-axis "Instancias" [1, 2, 4]
  y-axis "Respuestas/s" 0 --> 160
  line [58.78, 101.71, 141.93]
```

El punto 1×50 se observó una vez; para la capacidad certificada de una instancia se usa 1×25 repetido. El punto 4×100 se repitió tres veces, pero su variabilidad hizo fallar los SLO.
