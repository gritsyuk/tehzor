# ![logo Tehzor](https://tehzor.com/images/components/Header/logo.svg)
![PyPI - Version](https://img.shields.io/pypi/v/tehzor)

## Асинхронный Python-клиент Tehzor Public API

> **Ветка в разработке (0.2.0.dev).** Идёт полное переписывание под все 73 метода
> [Tehzor Public API](https://api.tehzor.ru/docs) и MCP-сервер для LLM-агентов.
> План — [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md), статус — ниже.
> Опубликованная на PyPI версия 0.1.x имеет другой интерфейс (`TehzorAPI.create`).

### Принципы

* **Факт важнее спецификации.** `docs/openapi.json` — заявление разработчика API о доступных методах.
  Модели строятся по фактическим ответам, которые проверяют контрактные тесты
  (`pytest -m contract`). Найденные расхождения собраны в [docs/API_FACTS.md](docs/API_FACTS.md).
* **Бережно к серверу.** Ограничение частоты и параллельности, повторы только для безопасных операций
  в пределах бюджета времени, circuit breaker. Тяжёлые запросы (502 после ~30 с) не повторяются.
* **Запись под контролем.** Режим `read_only=True` блокирует изменяющие операции до отправки.
  Создание, изменение и удаление проверяются только на заглушках.

### Быстрый старт

```python
import asyncio
from tehzor import TehzorClient


async def main() -> None:
    async with TehzorClient(api_key="...") as thz:   # или переменная окружения TEHZOR_API_KEY
        print(await thz.objects.stages())
        print(await thz.objects.get("<id объекта>"))


asyncio.run(main())
```

### Разработка

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check . && .venv/bin/mypy
.venv/bin/pytest                  # unit-тесты, без сети
.venv/bin/pytest -m contract      # живое API, только чтение (нужны ключ и TEHZOR_SEED_OBJECT_ID)
```

### Статус

| Этап | Состояние |
|---|---|
| 0. Каркас (pyproject, ruff, mypy, CI) | готово |
| 1. Ядро: транспорт с защитой сервера, ошибки, реестр операций, пагинация | готово |
| 2. Модели (по фактическим ответам) | готово |
| 3. Контрактные тесты: 49 читающих операций на живом API | готово — 53 из 53 |
| 4. Изменяющие операции (24) на заглушках | — |
| 5. MCP-сервер | — |
| 6. Релиз 0.2.0 | — |
