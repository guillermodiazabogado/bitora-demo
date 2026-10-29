# Infraestructura

| Recurso | Configuración |
|---|---|
| Host | Windows, Ryzen 7 5700G, 16 hilos, ~13,9 GiB físicos |
| Laboratorio | Ubuntu WSL, 16 CPU visibles, 6,7 GiB RAM, 2 GiB swap |
| Contenedores | Docker Engine 29.1.3, overlayfs |
| Base | PostgreSQL 16, `max_connections=100` |
| Aplicación | 1/2/4 instancias; pool por proceso min 1/max 10 |
| Red | Loopback/bridge Docker; no representa red de evento |

Estado de ejecución: **PENDIENTE**.
