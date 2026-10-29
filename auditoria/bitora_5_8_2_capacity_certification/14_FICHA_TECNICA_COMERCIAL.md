# Ficha técnica comercial

Perfiles orientativos de laboratorio; no son planes comerciales aprobados ni garantía productiva:

| Perfil técnico | Configuración mínima sugerida | Uso defendible | Estado |
|---|---|---|---|
| Event | 2 instancias + PostgreSQL 16 | ≥38,045 insc/s sostenidas; QR8 observado | laboratorio condicionado |
| Business | 4 instancias + PostgreSQL 16 | ráfaga ≥52,412 insc/s; sostenido 4×50 no cumplió p95 | requiere ajuste/prueba |
| Enterprise | dimensionamiento dedicado | requiere dataset 10k–50k, generador separado y red real | NO CERTIFICADO |

Por cantidad nominal: 1.000 participantes puede usar provisionalmente Event; 5.000, 10.000 y 25.000 requieren prueba de cardinalidad antes de recomendación firme. La cantidad almacenada no equivale a concurrencia.
