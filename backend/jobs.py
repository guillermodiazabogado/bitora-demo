from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import Queue
from typing import Any


@dataclass
class Job:
    kind: str
    payload: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


class JobQueue:
    """Small local queue abstraction.

    In production this can be replaced by Redis/RQ, Celery, Dramatiq, Sidekiq,
    SQS, or another durable queue without changing callers.
    """

    def __init__(self) -> None:
        self._queue: Queue[Job] = Queue()

    def enqueue(self, kind: str, payload: dict[str, Any]) -> Job:
        job = Job(kind=kind, payload=payload)
        self._queue.put(job)
        return job

    def size(self) -> int:
        return self._queue.qsize()


default_queue = JobQueue()
