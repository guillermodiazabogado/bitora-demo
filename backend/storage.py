from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any


class StorageConfigurationError(RuntimeError):
    pass


class StorageService:
    """Storage boundary with local and S3-compatible backends."""

    CATEGORIES = {"landing", "qr", "certificates", "exports", "attachments", "backups"}
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
        self.backend = self._normalize_backend(backend)
        if self.backend not in {"local", "s3", "r2"}:
            raise ValueError("STORAGE_BACKEND debe ser local, s3 o r2")
        self.bucket = self._env("R2_BUCKET", "S3_BUCKET")
        self.prefix = self._clean_prefix(self._env("R2_PREFIX", "S3_PREFIX", default="staging"))
        self._client: Any | None = None

    @property
    def ready(self) -> bool:
        if self.backend == "local":
            return True
        return bool(self.bucket and self._endpoint() and self._env("R2_ACCESS_KEY_ID", "S3_ACCESS_KEY_ID") and self._env("R2_SECRET_ACCESS_KEY", "S3_SECRET_ACCESS_KEY"))

    def check(self) -> dict:
        if not self.ready:
            return {"ok": False, "backend": self.backend, "detail": "storage incompleto"}
        if self.backend == "local":
            try:
                self.ensure()
                return {"ok": True, "backend": self.backend, "detail": "local ready"}
            except OSError as exc:
                return {"ok": False, "backend": self.backend, "detail": str(exc)}
        try:
            self._s3_client().list_objects_v2(Bucket=self.bucket, Prefix=self._remote_key("health"), MaxKeys=1)
            return {"ok": True, "backend": self.backend, "detail": "remote ready"}
        except Exception as exc:
            return {"ok": False, "backend": self.backend, "detail": str(exc)[:180]}

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
        if self.backend != "local":
            category = self._validate_category(category, self.CATEGORIES, "Categoria de storage invalida")
            safe_name = self._safe_name(name)
            key = f"{category}/{safe_name}"
            return self._put_record(key, content)
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
        if self.backend != "local":
            category = self._validate_category(category, self.CATEGORIES, "Categoria de storage invalida")
            return self.read_key(f"{category}/{self._safe_name(name)}")
        return self._path(category, name).read_bytes()

    def delete(self, category: str, name: str) -> bool:
        if self.backend != "local":
            category = self._validate_category(category, self.CATEGORIES, "Categoria de storage invalida")
            return self.delete_key(f"{category}/{self._safe_name(name)}")
        path = self._path(category, name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def inventory(self) -> list[dict]:
        if self.backend != "local":
            return self._list_records("")
        if not self.root.exists():
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
        if self.backend != "local":
            category = self._validate_category(category, self.EVENT_CATEGORIES, "Categoria de evento invalida")
            key = f"events/{self._event_id(event_id)}/{category}/{self._safe_name(name)}"
            return self._put_record(key, content)
        path = self._event_path(event_id, category, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return self._file_record(path)

    def read_event(self, event_id: int, category: str, name: str) -> bytes:
        if self.backend != "local":
            category = self._validate_category(category, self.EVENT_CATEGORIES, "Categoria de evento invalida")
            return self.read_key(f"events/{self._event_id(event_id)}/{category}/{self._safe_name(name)}")
        return self._event_path(event_id, category, name).read_bytes()

    def delete_event(self, event_id: int, category: str, name: str) -> bool:
        if self.backend != "local":
            category = self._validate_category(category, self.EVENT_CATEGORIES, "Categoria de evento invalida")
            return self.delete_key(f"events/{self._event_id(event_id)}/{category}/{self._safe_name(name)}")
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
            return self._list_records(f"events/{self._event_id(event_id)}/")
        root = self.event_root(event_id)
        if not root.exists():
            return []
        return [self._file_record(path) for path in sorted(item for item in root.rglob("*") if item.is_file())]

    def event_size(self, event_id: int) -> int:
        return sum(int(item["size"]) for item in self.event_inventory(event_id))

    def restore_event_file(self, event_id: int, relative_path: str, content: bytes) -> dict:
        if self.backend != "local":
            key = self._event_relative_key(event_id, relative_path)
            return self._put_record(key, content)
        path = self._event_relative_path(event_id, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return self._file_record(path)

    def delete_event_files(self, event_id: int) -> bool:
        if self.backend != "local":
            deleted = False
            for item in self.event_inventory(event_id):
                deleted = self.delete_key(item["key"]) or deleted
            return deleted
        root = self.event_root(event_id)
        if not root.exists():
            return False
        shutil.rmtree(root)
        return True

    def _path(self, category: str, name: str) -> Path:
        if self.backend != "local":
            raise RuntimeError("El adaptador S3 esta preparado pero no habilitado")
        category = self._validate_category(category, self.CATEGORIES, "Categoria de storage invalida")
        safe_name = self._safe_name(name)
        path = (self.root / category / safe_name).resolve()
        category_root = (self.root / category).resolve()
        if category_root not in path.parents:
            raise ValueError("Ruta de storage invalida")
        return path

    def _event_path(self, event_id: int, category: str, name: str) -> Path:
        category = self._validate_category(category, self.EVENT_CATEGORIES, "Categoria de evento invalida")
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

    def _event_relative_key(self, event_id: int, relative_path: str) -> str:
        parts = [part.strip() for part in str(relative_path or "").replace("\\", "/").split("/") if part.strip()]
        if not parts or parts[0] not in self.EVENT_CATEGORIES:
            raise ValueError("Ruta de archivo de evento invalida")
        if any(part in {".", ".."} or part != Path(part).name for part in parts):
            raise ValueError("Ruta de archivo de evento invalida")
        return "/".join(["events", str(self._event_id(event_id)), *parts])

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

    def read_key(self, key: str) -> bytes:
        key = self._safe_key(key)
        if self.backend == "local":
            path = (self.root / key).resolve()
            root = self.root.resolve()
            if root not in path.parents:
                raise ValueError("Ruta de storage invalida")
            return path.read_bytes()
        response = self._s3_client().get_object(Bucket=self.bucket, Key=self._remote_key(key))
        return response["Body"].read()

    def delete_key(self, key: str) -> bool:
        key = self._safe_key(key)
        if self.backend == "local":
            path = (self.root / key).resolve()
            root = self.root.resolve()
            if root not in path.parents or not path.exists():
                return False
            path.unlink()
            return True
        self._s3_client().delete_object(Bucket=self.bucket, Key=self._remote_key(key))
        return True

    def _put_record(self, key: str, content: bytes) -> dict:
        key = self._safe_key(key)
        digest = hashlib.sha256(content).hexdigest()
        content_type = "application/pdf" if key.lower().endswith(".pdf") else "application/octet-stream"
        self._s3_client().put_object(
            Bucket=self.bucket,
            Key=self._remote_key(key),
            Body=content,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )
        return {"backend": self.backend, "key": key, "size": len(content), "sha256": digest}

    def _list_records(self, prefix: str) -> list[dict]:
        if not self.ready:
            return []
        prefix = self._safe_key(prefix) if prefix else ""
        remote_prefix = self._remote_key(prefix)
        paginator = self._s3_client().get_paginator("list_objects_v2")
        items = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=remote_prefix):
            for obj in page.get("Contents", []):
                remote_key = str(obj.get("Key") or "")
                key = self._local_key(remote_key)
                if not key:
                    continue
                head = self._s3_client().head_object(Bucket=self.bucket, Key=remote_key)
                digest = (head.get("Metadata") or {}).get("sha256", "")
                items.append({"key": key, "size": int(obj.get("Size") or 0), "sha256": digest})
        return sorted(items, key=lambda item: item["key"])

    def _s3_client(self):
        if not self.ready:
            raise StorageConfigurationError("Storage remoto incompleto")
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise StorageConfigurationError("Falta dependencia boto3 para storage remoto") from exc
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint(),
                aws_access_key_id=self._env("R2_ACCESS_KEY_ID", "S3_ACCESS_KEY_ID"),
                aws_secret_access_key=self._env("R2_SECRET_ACCESS_KEY", "S3_SECRET_ACCESS_KEY"),
                region_name=self._env("R2_REGION", "S3_REGION", default="auto"),
                config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
            )
        return self._client

    def _endpoint(self) -> str:
        endpoint = self._env("R2_ENDPOINT", "S3_ENDPOINT_URL")
        if endpoint:
            return endpoint.rstrip("/")
        account_id = self._env("R2_ACCOUNT_ID")
        return f"https://{account_id}.r2.cloudflarestorage.com" if account_id else ""

    def _remote_key(self, key: str) -> str:
        return f"{self.prefix}/{self._safe_key(key)}" if self.prefix else self._safe_key(key)

    def _local_key(self, remote_key: str) -> str:
        remote_key = str(remote_key or "").strip("/")
        if self.prefix:
            prefix = f"{self.prefix}/"
            if not remote_key.startswith(prefix):
                return ""
            return remote_key[len(prefix):]
        return remote_key

    def _safe_key(self, key: str) -> str:
        parts = [part.strip() for part in str(key or "").replace("\\", "/").split("/") if part.strip()]
        if any(part in {".", ".."} or part != Path(part).name for part in parts):
            raise ValueError("Ruta de storage invalida")
        if not parts:
            raise ValueError("Ruta de storage invalida")
        return "/".join(parts)

    def _safe_name(self, name: str) -> str:
        raw_name = str(name or "").strip()
        safe_name = Path(raw_name).name
        if safe_name != raw_name or "/" in raw_name or "\\" in raw_name:
            raise ValueError("Nombre de archivo invalido")
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError("Nombre de archivo invalido")
        return safe_name

    def _validate_category(self, category: str, allowed: set[str], message: str) -> str:
        value = str(category or "").strip().lower()
        if value not in allowed:
            raise ValueError(message)
        return value

    def _env(self, *names: str, default: str = "") -> str:
        for name in names:
            value = os.environ.get(name, "").strip()
            if value:
                return value
        return default

    def _normalize_backend(self, backend: str) -> str:
        value = str(backend or os.environ.get("BITORA_STORAGE_PROVIDER") or "local").strip().lower()
        return {"cloudflare_r2": "r2", "cloudflare-r2": "r2"}.get(value, value)

    def _clean_prefix(self, prefix: str) -> str:
        value = str(prefix or "").strip().strip("/")
        if not value:
            return ""
        return self._safe_key(value)

    def _prune_empty_dirs(self, current: Path, stop_at: Path) -> None:
        current = current.resolve()
        stop_at = stop_at.resolve()
        while current != stop_at and stop_at in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
