"""Настройки MCP-сервера из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "да"}


def _float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value else default


def _int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def _set(name: str) -> frozenset[str]:
    value = os.environ.get(name, "")
    return frozenset(x.strip() for x in value.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    # клиент
    api_key: str | None = None
    user_id: str | None = None
    base_url: str = "https://api.tehzor.ru"
    proxy: str | None = None
    ssl_verify: bool = True
    max_concurrency: int = 5
    rate_limit: float = 5.0
    # запись и контроль человека (docs/DEVELOPMENT_PLAN.md, §5a)
    allow_write: bool = False
    """Без TEHZOR_MCP_ALLOW_WRITE=1 изменяющие инструменты отказывают и ничего не отправляют."""
    write_tools: frozenset[str] = field(default_factory=frozenset)
    """Если задан — запись разрешена только этими инструментами (TEHZOR_MCP_WRITE_TOOLS=a,b)."""
    hide_write_tools: bool = False
    """TEHZOR_MCP_HIDE_WRITE=1 — не регистрировать изменяющие инструменты вовсе (меньше контекста для LLM)."""
    confirm_ttl: float = 600.0
    audit_log: Path = field(default_factory=lambda: Path.home() / ".tehzor-mcp" / "audit.jsonl")
    # ответы
    default_limit: int = 50
    max_limit: int = 500
    search_max_items: int = 2000
    cache_ttl: float = 3600.0

    @classmethod
    def from_env(cls) -> Settings:
        audit = os.environ.get("TEHZOR_MCP_AUDIT_LOG")
        return cls(
            api_key=os.environ.get("TEHZOR_API_KEY") or None,
            user_id=os.environ.get("TEHZOR_USER_ID") or None,
            base_url=os.environ.get("TEHZOR_BASE_URL") or "https://api.tehzor.ru",
            proxy=os.environ.get("TEHZOR_PROXY") or None,
            ssl_verify=_bool("TEHZOR_SSL_VERIFY", True),
            max_concurrency=_int("TEHZOR_MAX_CONCURRENCY", 5),
            rate_limit=_float("TEHZOR_RATE_LIMIT", 5.0),
            allow_write=_bool("TEHZOR_MCP_ALLOW_WRITE"),
            write_tools=_set("TEHZOR_MCP_WRITE_TOOLS"),
            hide_write_tools=_bool("TEHZOR_MCP_HIDE_WRITE"),
            confirm_ttl=_float("TEHZOR_MCP_CONFIRM_TTL", 600.0),
            audit_log=Path(audit).expanduser() if audit else Path.home() / ".tehzor-mcp" / "audit.jsonl",
        )
