"""Ожидающие подтверждения изменяющие операции.

Превью хранит уже подготовленный запрос (PreparedRequest). При подтверждении отправляется ровно он,
поэтому подменить данные между превью и подтверждением нельзя. confirmation_id одноразовый и истекает.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from .._registry import Operation
from .._transport import PreparedRequest


@dataclass(frozen=True)
class Pending:
    confirmation_id: str
    op: Operation
    request: PreparedRequest
    digest: str
    expires_at: float


def digest(req: PreparedRequest) -> str:
    payload = json.dumps(
        [req.method, req.path, list(req.params), req.json], ensure_ascii=False, sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PendingStore:
    def __init__(self, ttl: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl = ttl
        self._clock = clock
        self._items: dict[str, Pending] = {}

    def add(self, op: Operation, request: PreparedRequest) -> Pending:
        self._purge()
        item = Pending(secrets.token_urlsafe(12), op, request, digest(request), self._clock() + self.ttl)
        self._items[item.confirmation_id] = item
        return item

    def pop(self, confirmation_id: str) -> Pending | None:
        """Одноразово забрать операцию; None — нет такой или истекла."""
        self._purge()
        item = self._items.pop(confirmation_id, None)
        if item is None or digest(item.request) != item.digest:
            return None
        return item

    def discard(self, confirmation_id: str) -> None:
        self._items.pop(confirmation_id, None)

    def _purge(self) -> None:
        now = self._clock()
        for key in [k for k, v in self._items.items() if v.expires_at <= now]:
            del self._items[key]

    def __len__(self) -> int:
        self._purge()
        return len(self._items)
