"""Объекты строительства, стадии, процессы. Сверено с живым API 2026-11-04 (docs/API_FACTS.md)."""

from __future__ import annotations

from typing import Any

from ._base import TehzorModel


class ConstructionObject(TehzorModel):
    """Объект (`GET /objects/{id}`).

    fact: `id` — UUID (новая архитектура), старый 24-hex id лежит в `external_id`.
    fact: `customFields` приходит как null, хотя в спецификации это обязательный объект.
    """

    id: str
    external_id: str | None = None
    name: str | None = None
    full_name: str | None = None
    parent_id: str | None = None
    company_id: str | None = None
    stage: str | None = None
    city: str | None = None
    address: str | None = None
    custom_fields: dict[str, Any] | None = None


class StageInfo(TehzorModel):
    """Стадия (`GET /stages`): building, acceptance, transfer, warranty."""

    id: str
    name: str | None = None


class ProcessInfo(TehzorModel):
    """Бизнес-процесс (`GET /processes`)."""

    id: str
    name: str | None = None


class HealthStatus(TehzorModel):
    """Ответ `GET /health/readiness` (метод не описан в openapi.json)."""

    status: str | None = None
