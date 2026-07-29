# BITORA V4.5 - Document Storage

Los documentos se guardan bajo storage de evento mediante `StorageService.save_event`.

Validaciones:

- nombre sin traversal;
- extension permitida;
- MIME permitido;
- tamano maximo 8 MB;
- ownership de organizacion y evento;
- respuesta API sin `storage_key` salvo contexto privado.
