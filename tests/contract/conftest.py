"""Контрактные тесты: живое API, СТРОГО только чтение.

Запуск: `pytest -m contract`. Нужен доступ к api.tehzor.ru и ключ (TEHZOR_API_KEY или прокси,
подставляющий заголовок api-key). Клиент создаётся с read_only=True: любая изменяющая операция
бросает ReadOnlyError до отправки запроса.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

from tehzor import TehzorClient


def seed(name: str) -> str:
    value = os.environ.get(f"TEHZOR_SEED_{name}")
    if not value:
        pytest.skip(f"не задан TEHZOR_SEED_{name}")
    return value


@pytest.fixture
async def live() -> AsyncIterator[TehzorClient]:
    async with TehzorClient(read_only=True, rate_limit=2.0, max_concurrency=2) as thz:
        yield thz
