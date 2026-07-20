from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path


class StorageService:
    """Local storage boundary prepared for a future S3-compatible adapter."""

    CATEGORIES = {"landing", "qr", "certificates", "exports", "attachments"}
    SYSTEM_CATEGORIES = {"branding", "icons", "logos", "providers"}
    EVENT_CATEGORIES = {
        "qr",
        "credentials",
        "certificates",
        "uploads",
        "exports",
        "attachments",
        "communications",
        "images",
        "public",
    }

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
        for category in self.SYSTEM_CATEGORIES:
            (self.root / "system" / category).mkdir(parents=True, exist_ok=True)
        (self.root / "events").mkdir(exist_ok=True)
        (self.root / "temporary").mkdir(exist_ok=True)
        (self.root / "backups" / "event").mkdir(parents=True, exist_ok=True)
        (self.root / "backups" / "full").mkdir(parents=True, exist_ok=True)

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

    def save_event(self, event_id: int, category: str, name: str, content: bytes) -> dict:
        path = self._event_path(event_id, category, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return self._file_record(path)

    def read_event(self, event_id: int, category: str, name: str) -> bytes:
        return self._event_path(event_id, category, name).read_bytes()

    def delete_event(self, event_id: int, category: str, name: str) -> bool:
        path = self._event_path(event_id, category, name)
        if not path.exists():
            return False
        path.unlink()
        self._prune_empty_dirs(path.parent, self.event_root(event_id))
        return True

    def event_root(self, event_id: int) -> Path:
        event_id = self._event_id(event_id)
        root = (self.root / "events" / str(event_id)).resolve()
        storage_root = self.root.resolve()
        if storage_root not in root.parents:
            raise ValueError("Ruta de evento invalida")
        return root

    def event_inventory(self, event_id: int) -> list[dict]:
        if self.backend != "local":
            return []
        root = self.event_root(event_id)
        if not root.exists():
            return []
        return [self._file_record(path) for path in sorted(item for item in root.rglob("*") if item.is_file())]

    def event_size(self, event_id: int) -> int:
        return sum(int(item["size"]) for item in self.event_inventory(event_id))

    def restore_event_file(self, event_id: int, relative_path: str, content: bytes) -> dict:
        path = self._event_relative_path(event_id, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return self._file_record(path)

    def delete_event_files(self, event_id: int) -> bool:
        root = self.event_root(event_id)
        if not root.exists():
            return False
        shutil.rmtree(root)
        return True

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

    def _event_path(self, event_id: int, category: str, name: str) -> Path:
        category = str(category or "").strip().lower()
        if category not in self.EVENT_CATEGORIES:
            raise ValueError("Categoria de evento invalida")
        return self._event_relative_path(event_id, f"{category}/{name}")

    def _event_relative_path(self, event_id: int, relative_path: str) -> Path:
        if self.backend != "local":
            raise RuntimeError("El adaptador S3 esta preparado pero no habilitado")
        root = self.event_root(event_id)
        parts = [part.strip() for part in str(relative_path or "").replace("\\", "/").split("/") if part.strip()]
        if not parts or parts[0] not in self.EVENT_CATEGORIES:
            raise ValueError("Ruta de archivo de evento invalida")
        if any(part in {".", ".."} or part != Path(part).name for part in parts):
            raise ValueError("Ruta de archivo de evento invalida")
        path = (root.joinpath(*parts)).resolve()
        if root not in path.parents:
            raise ValueError("Ruta de archivo de evento invalida")
        return path

    def _event_id(self, event_id: int) -> int:
        try:
            value = int(event_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("event_id invalido") from exc
        if value <= 0:
            raise ValueError("event_id invalido")
        return value

    def _file_record(self, path: Path) -> dict:
        content = path.read_bytes()
        return {
            "backend": self.backend,
            "key": path.relative_to(self.root).as_posix(),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def _prune_empty_dirs(self, current: Path, stop_at: Path) -> None:
        current = current.resolve()
        stop_at = stop_at.resolve()
        while current != stop_at and stop_at in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
