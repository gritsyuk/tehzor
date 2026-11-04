# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии — [SemVer](https://semver.org/lang/ru/).

## [0.2.0] — 2026-11-04

Полное переписывание. **Несовместимо с 0.1.x** — см. [docs/MIGRATION.md](docs/MIGRATION.md).

### Добавлено
- Все 73 операции Tehzor Public API v1.44.0 (49 на чтение, 23 на запись, 1 удаление) + недокументированный
  `GET /health/readiness`. Ресурсы: `objects`, `problems`, `spaces`, `space_owners`, `work_acceptances`,
  `internal_acceptances`, `owner_acceptances`, `warranty_claims`, `tasks`, `comments`, `categories`, `tags`,
  `check_lists`, `checks`.
- `TehzorClient` с `async with`, автопагинация `iter()` (страница 50, уменьшение вдвое при тяжёлом запросе).
- Модели по **фактическим** ответам API (контрактные тесты), а не по `openapi.json`: обязателен только `id`,
  неизвестные поля сохраняются; расхождения со спецификацией — в [docs/API_FACTS.md](docs/API_FACTS.md).
- Защита сервера: таймауты 10/35 с, ограничение частоты (5 запросов/с) и параллельности (5), повторы только
  безопасных операций с бюджетом времени и `Retry-After`, circuit breaker, `QueryTooHeavyError` вместо повтора
  тяжёлого запроса (502 после ~30 с).
- Запись под контролем: `dry_run=True` (подготовленный запрос без отправки), `read_only=True`; создание
  никогда не повторяется автоматически; проверка тел запросов до отправки (`extra="forbid"`, enum).
- MCP-сервер `tehzor-mcp` (`pip install "tehzor[mcp]"`): 76 инструментов, 18 ресурсов-справочников,
  `problems_search`, `space_overview`; запись выключена по умолчанию, каждая изменяющая операция — только после
  подтверждения человеком (elicitation или `confirm_operation`), журнал аудита; stdio и HTTP с Bearer-токеном;
  запуск через `uvx` и Docker.
- Тесты: 241 unit-тест на заглушках (сеть недоступна по построению), контрактные тесты на живом API
  (`pytest -m contract`, строго только чтение), песочница для ручной проверки записи (`tests/sandbox`).
- CI: ruff, mypy (strict), тесты на Python 3.10–3.13, сборка пакета и Docker-образа, ночной контрактный прогон,
  публикация на PyPI через Trusted Publishing.

### Изменено
- Python ≥ 3.10 (было объявлено ≥ 3.6 при фактическом требовании 3.10+).
- Сборка на `pyproject.toml` (hatchling) вместо `setup.py`.
- SSL-сертификаты проверяются по умолчанию (в 0.1.x проверка была выключена).
- Даты — `datetime` в UTC (в 0.1.x — наивное локальное время или int).

### Исправлено
- Ошибка одного запроса больше не закрывает общую HTTP-сессию.
- `SpaceUpdate(area_bti=…)` молча терял площадь БТИ — `SpaceEdit` отправляет `areaBTI`.
- `ProblemLinks.workAcceptanceId` не разбирался; приёмка работ больше не наследуется от нарушения и не требует
  несуществующего `acceptanceDate`; `typeDecoration` помещения — объект `{id, name}`.
- Проверки ответов через `assert` заменены исключениями с телом ответа.

### Удалено
- `TehzorAPI`, `tehzor.constants.CONSTRUCT_STAGES` (используйте `objects.stages()` / `objects.processes()`),
  старые модели, корневые `config.py`, `utils.py`, `publish.py`, `setup.py`.

## [0.1.3]
- Последняя версия старого интерфейса `TehzorAPI.create(...)`.
