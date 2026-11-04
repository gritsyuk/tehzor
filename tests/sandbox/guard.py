"""Транспорт-песочница для ручных прогонов изменяющих операций на живом API.

Правило: изменять и удалять можно ТОЛЬКО сущности, созданные в этом же прогоне
(плюс явно разрешённые тестовые id). Любой другой изменяющий запрос блокируется до отправки.
Создание (операции без id в пути) разрешено. Каждый изменяющий запрос пишется в журнал.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tehzor._registry import Operation
from tehzor._transport import PreparedRequest, Transport
from tehzor.errors import ReadOnlyError

# параметры пути, которые являются значениями статусов, а не id сущностей
NON_ENTITY_PARAMS = {
    "spaceStatusId",
    "checkListStatus",
    "checkItemStatus",
    "ownerAcceptanceStatusId",
    "ownerAcceptanceResolutionsId",
}
ENTITY_QUERY_PARAMS = {"spaceId", "checkItemId"}


class SandboxViolation(ReadOnlyError):
    """Попытка изменить сущность, не созданную в этом прогоне."""


class SandboxTransport(Transport):
    def __init__(self, journal: Path, *, allowed_ids: set[str] | None = None, **kwargs: Any) -> None:
        super().__init__(rate_limit=1.0, max_concurrency=1, retries=0, **kwargs)
        self.created: set[str] = set()
        self.allowed_ids = set(allowed_ids or ())
        self.journal = journal
        journal.parent.mkdir(parents=True, exist_ok=True)

    def track(self, entity_id: str | None, what: str) -> None:
        if entity_id:
            self.created.add(entity_id)
            self._log({"event": "created", "what": what, "id": entity_id})

    def untrack(self, entity_id: str) -> None:
        self.created.discard(entity_id)

    def _log(self, record: dict[str, Any]) -> None:
        record["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with self.journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def check(
        self, op: Operation, path_params: dict[str, Any] | None, params: dict[str, Any] | None, json: Any = None
    ) -> None:
        if op.kind == "R":
            return
        if isinstance(json, dict) and json.get("unbindExistingOwners"):
            # отвязало бы реальных собственников помещения — это изменение существующих данных
            raise SandboxViolation("песочница: unbindExistingOwners=true запрещён — запрос не отправлен")
        targets = [str(getattr(v, "value", v)) for k, v in (path_params or {}).items() if k not in NON_ENTITY_PARAMS]
        targets += [str(v) for k, v in (params or {}).items() if k in ENTITY_QUERY_PARAMS and v is not None]
        foreign = [t for t in targets if t not in self.created and t not in self.allowed_ids]
        if foreign:
            raise SandboxViolation(
                f"песочница: {op.tool_name} затрагивает id {foreign}, не созданные в этом прогоне — запрос не отправлен"
            )

    async def execute(self, op: Operation, **kwargs: Any) -> Any:
        self.check(op, kwargs.get("path_params"), kwargs.get("params"), kwargs.get("json"))
        if op.kind == "R":
            return await super().execute(op, **kwargs)
        req = self.prepare(op, **kwargs)
        self._log({"event": "send", "tool": op.tool_name, "request": req.describe(), "json": req.json})
        try:
            result = await self.send(req, can_retry=False)
        except Exception as exc:
            self._log({"event": "error", "tool": op.tool_name, "error": f"{type(exc).__name__}: {exc}"})
            raise
        self._log({"event": "ok", "tool": op.tool_name, "response_keys": _keys(result)})
        return result


def _keys(value: Any) -> Any:
    if isinstance(value, dict):
        return sorted(value)
    if isinstance(value, list):
        return [_keys(value[0])] if value else []
    return type(value).__name__


def describe(req: PreparedRequest) -> str:
    return f"{req.describe()}\n    тело: {json.dumps(req.json, ensure_ascii=False) if req.json is not None else '—'}"
