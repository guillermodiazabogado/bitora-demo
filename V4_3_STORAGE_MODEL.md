# V4.3 Storage Model

Los PDF se guardan bajo:

`storage/events/{event_id}/certificates/`

El servicio de storage valida rutas, categorias y traversal. El documento se lee nuevamente para verificar su hash antes de descargar.
