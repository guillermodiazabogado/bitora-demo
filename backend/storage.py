from __future__ import annotations

import hashlib
import os
from pathlib import Path


class StorageService:
    """Local storage boundary prepared for a future S3-compatible adapter."""

    CATEGORIES = {"landing", "qr", "certificates", "exports", "attachments"}

    def __init__(self, root: Path, backend: str = "local") -> None:
        self.root = Path(root)
        self.backend = str(backend or "local").strip().lower()
        if self.backend not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND debe ser local o s3")

    @property
    def ready(self) -> bool:
        return self.backend == "local" or bool(os.environ.get("S3_BUCKET"))

    def ensure(self) -> None:
        if self.backend != "local":
            return
        self.root.mkdir(parents=True, exist_ok=True)
        for category in self.CATEGORIES:
            (self.root / category).mkdir(exist_ok=True)

    def save(self, category: str, name: str, content: bytes) -> dict:
        path = self._path(category, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {
            "backend": self.backend,
            "key": f"{category}/{path.name}",
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def read(self, category: str, name: str) -> bytes:
        return self._path(category, name).read_bytes()

    def delete(self, category: str, name: str) -> bool:
        path = self._path(category, name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def inventory(self) -> list[dict]:
        if self.backend != "local" or not self.root.exists():
            return []
        items = []
        for path in sorted(item for item in self.root.rglob("*") if item.is_file()):
            content = path.read_bytes()
            items.append(
                {
                    "key": path.relative_to(self.root).as_posix(),
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
        return items

    def _path(self, category: str, name: str) -> Path:
        if self.backend != "local":
            raise RuntimeError("El adaptador S3 esta preparado pero no habilitado")
        category = str(category or "").strip().lower()
        if category not in self.CATEGORIES:
            raise ValueError("Categoria de storage invalida")
        raw_name = str(name or "").strip()
        safe_name = Path(raw_name).name
        if safe_name != raw_name or "/" in raw_name or "\\" in raw_name:
            raise ValueError("Nombre de archivo invalido")
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError("Nombre de archivo invalido")
        path = (self.root / category / safe_name).resolve()
        category_root = (self.root / category).resolve()
        if category_root not in path.parents:
            raise ValueError("Ruta de storage invalida")
        return path
