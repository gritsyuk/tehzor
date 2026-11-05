# ![logo Tehzor](https://tehzor.com/wp-content/themes/tehzor/src/img/logo.svg)
![PyPI - Version](https://img.shields.io/pypi/v/tehzor)

## Асинхронный Python-клиент Tehzor Public API

Все 73 метода [Tehzor Public API](https://api.tehzor.ru/docs) и MCP-сервер для LLM-агентов.

```bash
pip install -U tehzor            # библиотека
pip install -U "tehzor[mcp]"     # + MCP-сервер tehzor-mcp
```

> **0.2.0 несовместима с 0.1.x** (`TehzorAPI.create`) — см. [docs/MIGRATION.md](docs/MIGRATION.md) и
> [CHANGELOG.md](CHANGELOG.md). Примеры — в [examples/](examples/).

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
from tehzor.models.problems import ProblemFilters
from tehzor.models.spaces import SpaceEdit


async def main() -> None:
    async with TehzorClient(api_key="...") as thz:   # или переменная окружения TEHZOR_API_KEY
        print(await thz.objects.stages())
        async for p in thz.problems.iter(ProblemFilters(objects=["<id объекта>"])):
            print(p.number, p.status.name if p.status else None)

        # изменения: сначала посмотреть запрос, ничего не отправляя
        req = await thz.spaces.edit("<id помещения>", SpaceEdit(area_bti=55.1), dry_run=True)
        print(req.describe(), req.json)


asyncio.run(main())
```

## MCP-сервер для LLM-агентов

`tehzor-mcp` публикует все 73 операции API как инструменты MCP, плюс аналитику (см. ниже), `space_overview`
(сводка по помещению) и справочники как ресурсы `tehzor://…`.

### Запуск

**uvx** (без установки):

```bash
uvx --from "tehzor[mcp]" tehzor-mcp
```

Из git (например, ветка до релиза): `uvx --from "tehzor[mcp] @ git+https://github.com/gritsyuk/tehzor@<ветка>" tehzor-mcp`.

**Docker:**

```bash
docker build -t tehzor-mcp .
```

```bash
docker run -i --rm -e TEHZOR_API_KEY tehzor-mcp
```

За корпоративным прокси с собственным CA сертификат передаётся только на время сборки:
`docker build --build-arg HTTPS_PROXY --secret id=pip_ca,src=/path/to/ca.pem -t tehzor-mcp .`

**HTTP (streamable-http)** — для удалённого подключения, только с токеном:

```bash
TEHZOR_API_KEY=… TEHZOR_MCP_HTTP_TOKEN=$(openssl rand -hex 32) docker compose up -d
```

Клиент подключается к `http://<host>:8000/mcp` с заголовком `Authorization: Bearer <TEHZOR_MCP_HTTP_TOKEN>`.
Наружу публикуйте только за reverse-proxy с TLS.

### Подключение

Claude Code:

```bash
claude mcp add tehzor --env TEHZOR_API_KEY=… -- uvx --from "tehzor[mcp]" tehzor-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "tehzor": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "TEHZOR_API_KEY", "tehzor-mcp"],
      "env": {"TEHZOR_API_KEY": "…"}
    }
  }
}
```

### Аналитика

| Инструмент | Что делает |
|---|---|
| `objects_discover` | все объекты компании деревом (ЖК → корпус → секция), новые с прошлого обхода |
| `problems_summary` | открыто / просрочено / критично по объектам, видам работ, организациям и исполнителям |
| `problems_search` | нарушения по объектам или коду проекта, `include_children` — с корпусами и секциями |
| `work_acceptances_search` | приёмки работ сразу по нескольким объектам и статусам |
| `projects_list`, `project_resolve` | проекты из таблицы соответствий и их объекты |

Правила сводки: открыто — «К устранению», «В работе», «На проверке»; просрочено — открыто и срок устранения прошёл;
считается по текущему состоянию (истории статусов в API нет). Сервер сам дочерние объекты не учитывает — для
корпусов и секций передавайте `include_children=true` (в `problems_summary` включено по умолчанию).

**Соответствие объектов проектам** (`TEHZOR_MCP_PROJECTS`) — необязательно; без него всё работает по UUID.
Каталог MD-файлов (граф знаний) с frontmatter:

```markdown
---
code: SIG
title: ЖК «Аквилон Signal»
tehzor:                # UUID объектов Техзора (ЖК — дочерние подтянутся сами)
  - 00000000-0000-4000-8000-000000000001
---
Описание проекта…
```

Также подходят `.json` / `.yaml` (`[{code, name, objects: [uuid…], card}]`) и `.csv`
(`object_id,project_code,project_name,card`). Файлы перечитываются при изменении.

### Запись данных и подтверждение человеком

* По умолчанию **запись выключена**: изменяющие инструменты видны агенту, но отказывают и ничего не отправляют.
  Включается `TEHZOR_MCP_ALLOW_WRITE=1`; `TEHZOR_MCP_WRITE_TOOLS=problems_create,comments_create` сужает список.
  `TEHZOR_MCP_HIDE_WRITE=1` убирает изменяющие инструменты совсем.
* Даже при включённой записи **каждая** изменяющая операция сначала возвращает превью (метод, путь, тело) и
  одноразовый `confirmation_id` (живёт 10 минут). Выполнение — только после подтверждения человеком: через
  диалог клиента (MCP elicitation) или инструмент `confirm_operation`. Отправляется ровно показанный запрос.
* Создание никогда не повторяется автоматически (дублей не будет). Для большинства сущностей удаления в API нет.
* Журнал аудита — `TEHZOR_MCP_AUDIT_LOG` (по умолчанию `~/.tehzor-mcp/audit.jsonl`, в Docker — том `/data`);
  ФИО, телефоны и email маскируются, ключ не пишется.
* Важно: при создании нарушения сервер Tehzor сам назначает исполнителей и наблюдателей по настройкам
  объекта — они получают уведомления (см. [docs/API_FACTS.md](docs/API_FACTS.md)).

### Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `TEHZOR_API_KEY` | — | ключ API (можно не задавать, если заголовок `api-key` подставляет прокси) |
| `TEHZOR_BASE_URL` | `https://api.tehzor.ru` | адрес API |
| `TEHZOR_PROXY`, `TEHZOR_SSL_VERIFY` | —, `1` | прокси и проверка TLS; также учитываются `HTTPS_PROXY`/`NO_PROXY` |
| `TEHZOR_RATE_LIMIT`, `TEHZOR_MAX_CONCURRENCY` | `5`, `5` | запросов в секунду и параллельно |
| `TEHZOR_MCP_ALLOW_WRITE` | `0` | разрешить изменяющие операции (с подтверждением) |
| `TEHZOR_MCP_WRITE_TOOLS` | все | список разрешённых изменяющих инструментов |
| `TEHZOR_MCP_HIDE_WRITE` | `0` | не публиковать изменяющие инструменты |
| `TEHZOR_MCP_CONFIRM_TTL` | `600` | срок жизни `confirmation_id`, с |
| `TEHZOR_MCP_AUDIT_LOG` | `~/.tehzor-mcp/audit.jsonl` | журнал аудита |
| `TEHZOR_MCP_TRANSPORT`, `TEHZOR_MCP_HOST`, `TEHZOR_MCP_PORT` | `stdio`, `127.0.0.1`, `8000` | транспорт |
| `TEHZOR_MCP_HTTP_TOKEN` | — | обязательный токен для HTTP |
| `TEHZOR_MCP_PROJECTS` | — | каталог MD или файл JSON/YAML/CSV: объект → проект |
| `TEHZOR_MCP_STATE_DIR` | `~/.tehzor-mcp` | снимок объектов для «новых с прошлого обхода» |

## Разработка

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check . && .venv/bin/mypy
.venv/bin/pytest                  # unit-тесты, без сети
.venv/bin/pytest -m contract      # живое API, только чтение (нужны ключ и TEHZOR_SEED_OBJECT_ID)
```

## Статус

| Этап | Состояние |
|---|---|
| 0. Каркас (pyproject, ruff, mypy, CI) | готово |
| 1. Ядро: транспорт с защитой сервера, ошибки, реестр операций, пагинация | готово |
| 2. Модели (по фактическим ответам) | готово |
| 3. Контрактные тесты: 49 читающих операций на живом API | готово — 53 из 53 |
| 4. Изменяющие операции (24): `dry_run`, только на заглушках | готово — 73 из 73 операций |
| 5. MCP-сервер: 76 инструментов, 18 ресурсов, подтверждение записи; uvx и Docker | готово |
| 6. Релиз 0.2.0: CHANGELOG, гайд миграции, примеры, публикация через Trusted Publishing | опубликовано на PyPI 05.11.2026 |
