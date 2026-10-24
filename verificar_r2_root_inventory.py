from __future__ import annotations

import os
from pathlib import Path

from backend.storage import StorageService


class EmptyPaginator:
    def paginate(self, **_kwargs):
        return [{"Contents": []}]


class EmptyS3Client:
    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        return EmptyPaginator()


def main() -> None:
    old_prefix = os.environ.get("R2_PREFIX")
    try:
        os.environ["R2_PREFIX"] = "production"
        storage = StorageService(Path("tmp/storage-r2-test"), "r2")
        storage._client = EmptyS3Client()
        storage.bucket = "bitora-test"
        assert storage._remote_key("") == "production/"
        assert storage._remote_key("exports/report.json") == "production/exports/report.json"
        assert storage.inventory() == []
    finally:
        if old_prefix is None:
            os.environ.pop("R2_PREFIX", None)
        else:
            os.environ["R2_PREFIX"] = old_prefix
    print("PASS R2 root inventory accepts configured prefix")


if __name__ == "__main__":
    main()
