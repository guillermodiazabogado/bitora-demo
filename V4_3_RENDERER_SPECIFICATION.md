# V4.3 Renderer Specification

Renderer: `bitora_certificate_renderer_v1`.

Usa ReportLab local, sin recursos externos ni fuentes remotas. El PDF se genera desde payload normalizado y version publicada. Se conserva:

- hash binario SHA-256 del PDF;
- hash logico del payload + contenido + renderer.

La prueba valida que el PDF sea descargable y que el hash almacenado coincida.
