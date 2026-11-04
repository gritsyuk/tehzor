"""Общие типы: временные метки API в миллисекундах."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, SerializationInfo


def _parse_timestamp(value: Any) -> Any:
    """Миллисекунды (int/float/строка из цифр) → datetime в UTC; остальное отдаём pydantic."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str) and value.isdigit():
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    return value


def to_millis(value: datetime) -> int:
    """datetime → миллисекунды Unix (наивный datetime считается UTC)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _serialize(value: datetime, info: SerializationInfo) -> int | str:
    """По умолчанию — миллисекунды (как ждёт API). С context={"timestamps": "iso"} — ISO 8601 (для MCP/LLM)."""
    ctx = info.context
    if isinstance(ctx, dict) and ctx.get("timestamps") == "iso":
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return to_millis(value)


Timestamp = Annotated[
    datetime,
    BeforeValidator(_parse_timestamp),
    PlainSerializer(_serialize, return_type=int | str, when_used="always"),
]
"""Временная метка API: в ответах — миллисекунды, в Python — datetime (UTC), в запросах — снова миллисекунды."""
