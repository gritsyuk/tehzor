# План: переписать `tehzor` под полный Public API v1.44.0 и MCP-сервер для LLM‑агента

## Context

Текущая обёртка (`tehzor/api.py`, 0.1.3) покрывает 13 из 73 операций Tehzor Public API v1.44.0. Часть моделей не совпадает со спецификацией: `WorkAcceptances` унаследована от `Problem` и требует несуществующее `acceptanceDate`, `typeDecoration` объявлен строкой, хотя это объект. Есть и системные дефекты: SSL выключен, при ошибке закрывается сессия, ответы проверяются через `assert`, пагинации нет, тестов без сети нет.

Цель — библиотека с полным соответствием 73 операциям и MCP‑сервер поверх неё, через который LLM‑агент работает с «Техзором».

Принятые решения:
- **Ломаем совместимость, выпускаем 0.2.0.** Старый `TehzorAPI` удаляется, в README будет гайд миграции.
- **MCP‑сервер живёт в этом же репозитории**: модуль `tehzor/mcp/`, extra `tehzor[mcp]`, команда `tehzor-mcp`.
- **Агенту доступны все 73 операции**, включая запись и удаление. Write и delete‑инструменты при этом получают MCP‑аннотации `destructiveHint`, чтобы клиент мог спрашивать подтверждение.

Источник истины — OpenAPI v1.44.0, который прислал пользователь. Он сохраняется в `docs/openapi.json`.

---

## 1. Целевая структура пакета

```
pyproject.toml                # hatchling; deps: aiohttp>=3.9,<4; pydantic>=2.6,<3
                              # extras: mcp = ["mcp>=1.2,<2"]; dev = [pytest, pytest-asyncio, aioresponses, ruff, mypy]
docs/openapi.json             # спецификация v1.44.0
scripts/check_spec_drift.py   # сверка моделей и реестра операций с openapi.json
scripts/record_fixtures.py    # запись реальных ответов в tests/fixtures (с обезличиванием)
tehzor/
  __init__.py                 # TehzorClient, исключения, __version__
  _version.py
  _transport.py               # aiohttp: ssl, таймауты, ретраи, семафор, маппинг ошибок
  _pagination.py              # Page / iter_pages
  _registry.py                # @operation(operation_id, ...) — реестр 73 операций
  errors.py                   # иерархия исключений
  client.py                   # TehzorClient (async context manager) + ресурсы
  types.py                    # Timestamp (мс <-> datetime UTC), enum-ы стадий/процессов/статусов
  models/
    _base.py                  # TehzorModel / TehzorRequest
    common.py                 # User, BriefUser, File, Location, Reason, ObjectRef, Status-DTO
    objects.py  spaces.py  space_owners.py  categories.py  check_lists.py  checks.py
    comments.py  work_acceptances.py  internal_acceptances.py  owner_acceptances.py
    warranty_claims.py  problems.py  tasks.py  tags.py
  resources/
    _base.py                  # BaseResource(transport)
    objects.py … tags.py      # по одному файлу на тег спецификации
  mcp/
    __init__.py
    server.py                 # FastMCP, lifespan, автогенерация tools из реестра
    __main__.py               # python -m tehzor.mcp
tests/
  unit/                       # aioresponses, без сети
  fixtures/                   # JSON-ответы по operationId
  integration/                # @pytest.mark.integration, нужен TEHZOR_API_KEY
examples/                     # переписанные примеры без config.py
```

Удаляются `tehzor/api.py`, `tehzor/constants.py` (заменяют `objects.stages()`/`processes()` и enum в `types.py`), корневые `config.py`, `utils.py`, `publish.py`, `setup.py`, а также `.env.exapmle` (вместо него `.env.example`).

## 2. Ядро

**`_transport.py`** — единственное место, где выполняется HTTP:
```python
class Transport:
    def __init__(self, api_key, base_url="https://api.tehzor.ru", *, proxy=None, ssl=True,
                 timeout=60, max_concurrency=10, retries=3): ...
    async def request(self, method, path, *, params=None, json=None) -> Any:
        # семафор -> session.request(..., ssl=self.ssl, proxy=self.proxy)
        # 2xx (200 и 201 одинаково) -> json или None при пустом теле
        # 429/502/503/504 и сетевые таймауты -> ретрай с экспоненциальной задержкой и учётом Retry-After
        # >=400 -> raise from_status(status, body)
```
- Массивы в query (`fields=a&fields=b`) сериализуются явно.
- `None` в `params` и `json` не отправляется.
- Логгер `tehzor` пишет метод, путь, статус и длительность; заголовок `api-key` в лог не попадает.

**`errors.py`**: `TehzorError` → `TehzorHTTPError(status, message, body, operation_id)`. От него наследуются `BadRequestError` (400), `UnauthorizedError` (401), `ForbiddenError` (403), `NotFoundError` (404), `ConflictError` (409), `RateLimitError` (429), `ServerError` (5xx). Отдельно `TehzorTimeoutError` и `TehzorConnectionError`.

**`client.py`**:
```python
async with TehzorClient(api_key=..., user_id=None) as thz:
    p = await thz.problems.get("…")
    async for p in thz.problems.iter(filters=ProblemFilters(objects=[…]), page_size=200):
        ...
```
Ресурсы: `objects`, `spaces`, `space_owners`, `categories`, `check_lists`, `checks`, `comments`, `work_acceptances`, `internal_acceptances`, `owner_acceptances`, `warranty_claims`, `problems`, `tasks`, `tags`. Плюс `health()` — он не описан в спецификации, но используется сейчас.

**Пагинация** для 6 списочных эндпоинтов с `limit`/`offset`: `get-problems`, `get-spaces`, `get-work-acceptances`, `get-internal-acceptances`, `get-comments`, `get-tasks`.
- `list(limit=20, offset=0, …) -> list[Model]` — одна страница.
- `iter(page_size=100, max_items=None, …) -> AsyncIterator[Model]` — загружает страницы, пока очередная не окажется короче `page_size`.

**`_registry.py`** — стержень всей схемы:
```python
@operation("ProblemsController_getOne", method="GET", path="/problems/{id}", read_only=True,
           summary="Возвращает нарушение по id")
async def get(self, id: str) -> Problem: ...
```
Реестр нужен трём потребителям:
1. тесту полноты: множество operationId из `openapi.json` должно совпасть с реестром;
2. MCP‑серверу, который сам генерирует инструменты;
3. `check_spec_drift.py`.

Есть тонкость: `ProblemsController_getProblems` в спецификации встречается дважды (`/internal-acceptances/{id}/problems` и `/warranty-claims/{id}/problems`). Поэтому ключ реестра — пара `method + path`, а operationId хранится как метаданные.

## 3. Модели

**Базовые классы** (`models/_base.py`):
```python
class TehzorModel(BaseModel):            # ответы
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True,
                              extra="allow", ser_json_timedelta="iso8601")
class TehzorRequest(BaseModel):          # тела запросов
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    def to_api(self) -> dict: return self.model_dump(by_alias=True, exclude_none=True, mode="json")
```

**Правила:**
- В ответных моделях обязателен только `id`, остальные поля `Optional` со значением `None`. Списки `required` в спецификации неточные: например, в `Edit*Dto` обязательны все поля.
- Тела запросов: обязательными делаем только поля, без которых операция по смыслу не выполнится (`CreateTaskDto`: `name`, `objectId`, `taskPriorityId`, `taskTypeId`), остальные опциональны. Отправляются через `exclude_none`.
- Временные метки — тип `Timestamp = Annotated[datetime, …]`. Принимает миллисекунды, отдаёт `datetime` в UTC, при сериализации запроса превращается обратно в миллисекунды.
- Имена, расходящиеся с camelCase, задаются явным `Field(alias=...)` при `populate_by_name=True`: `areaBTI`, `numberBTI`, `floorBTI`, `_id` в DTO передач собственникам. Это закрывает баг с потерей `area_bti`.
- Значения enum из спецификации (стадии, `processId`, статусы нарушений, задач, приёмок и передач, `CheckRecordStatusId`, типы задач и приёмок, `frontType`, `spaceTypes`) объявляются как `StrEnum`. В ответах поле имеет тип `StrEnum | str`, чтобы новое значение на сервере не ломало разбор.

**Известные расхождения спецификации, которые обрабатываем явно:**

| Место | Решение |
|---|---|
| 200 и 201 на POST (`/spaces/{id}`, `/space-owners`) | Транспорт считает успехом любой 2xx |
| `GetSpaceDto.typeDecoration` — объект, `EditSpaceSwaggerDto.typeDecoration` — id | Ответ: `SpaceTypeDecoration`; запрос: `type_decoration: str` |
| `attachments`: в спецификации строки, старый код ждал объекты | `list[str \| File \| dict]`; точный формат уточнить по записанным фикстурам |
| `/space-types-decorations`: в схеме один объект, в примере список | Принимаем и то и другое, наружу всегда `list[SpaceTypesDecorationsSet]` |
| `CreatableSpaceOwner.spaces.items: array` (ошибка в схеме) | `list[str]` |
| В фильтре нарушений `modifiedAtFrom/To` — строка, в остальных фильтрах — мс | В фильтре нарушений принимаем `datetime \| int \| str` и сериализуем по формату эндпоинта; формат уточнить на реальном API |
| `DELETE /space-owners/{ownerId}/delete`, у ответа пустой `$ref` | Возвращаем `None` или сырой JSON |
| `POST /owner-acceptances` возвращает строку‑id | Возвращаем `str` |
| `POST /work-acceptances` — массовое создание | `create_many(items) -> list[AddWorkAcceptanceResult]`. Ошибки по отдельным элементам (`error`, `errorDescription`) не превращаются в исключение, а возвращаются в результате |

**Построение моделей.** Черновик генерируется один раз командой `datamodel-code-generator --input docs/openapi.json --output-model-type pydantic_v2.BaseModel`. Затем модели вручную раскладываются по доменам и приводятся к правилам выше. `scripts/check_spec_drift.py` сравнивает `properties` каждой схемы с полями модели и выводит отличия. Это задел на будущие версии API: README предупреждает, что API меняется.

## 4. Ресурсы: полный маппинг 73 операций

(R — чтение, W — запись, D — удаление; MCP‑инструмент называется `<ресурс>_<метод>`)

| Ресурс | Методы → эндпоинт |
|---|---|
| `objects` (3) | `get(id)` GET `/objects/{id}` R · `stages()` GET `/stages` R · `processes()` GET `/processes` R |
| `spaces` (13) | `list/iter(filters: SpaceFilters)` POST `/spaces/get-spaces` R · `get(space_id)` GET `/spaces/{id}` R · `edit(space_id, SpaceEdit)` POST `/spaces/{id}` W · `set_status(space_id, status_id)` POST `/spaces/{id}/set-status/{statusId}` W · `get_status(space_id)` GET `/spaces/{id}/status` R · `meters(space_id)` GET `/spaces/{id}/meters` R · `owner_acceptances(space_id, fields)` R · `warranty_claims(space_id, fields)` R · `types()` `/space-types` R · `meter_types()` `/meter-types` R · `contract_forms()` `/contract-forms` R · `decoration_sets(fields)` `/space-types-decorations` R · `status_sets()` `/space-statuses` R |
| `space_owners` (6) | `create(SpaceOwnerCreate)` POST `/space-owners` W · `get_or_create(name, email, phone)` W · `edit(owner_id, …)` POST `/space-owners/{id}` W · `delete(owner_id)` DELETE `/space-owners/{id}/delete` D · `bind(owner_id, space_id, unbind_existing)` W · `unbind(owner_id, space_id)` W |
| `categories` (3) | `list(set_id)` GET `/categories` R · `create(CategoryCreate)` POST `/categories` W · `sets(object_id)` GET `/categories-sets` R |
| `check_lists` (8) | `list(object_id, stage)` R · `get(check_list_id)` R · `get_status(check_list_id, space_id)` R · `get_item_status(check_item_id, space_id)` R · `set_status(check_list_id, status, space_id, stage)` W · `set_item_status(check_list_id, check_item_id, status, space_id, stage)` W · `item_statuses()` R · `statuses()` R |
| `checks` (2) | `create(CheckCreate)` W · `get(id)` R |
| `comments` (3) | `get(id)` R · `list/iter(filters: CommentFilters)` R · `create(CommentCreate)` W |
| `work_acceptances` (7) | `get(id)` R · `list/iter(object_id, filters)` R · `edit(id, WorkAcceptanceEdit)` W · `create_many(list[WorkAcceptanceCreate])` W · `statuses()` R · `front_types()` R · `types()` R |
| `internal_acceptances` (4) | `list/iter(object_id)` R · `create(…)` W · `get(id)` R · `problems(id)` R |
| `owner_acceptances` (6) | `create(…) -> str` W · `get(id)` R · `set_status(id, status)` W · `set_resolution(id, resolution)` W · `resolutions()` R · `statuses()` R |
| `warranty_claims` (4) | `get(id)` R · `create(WarrantyClaimCreate)` W · `problems(id, fields)` R · `statuses()` R |
| `problems` (6) | `create(ProblemCreate)` W · `list/iter(user_id, filters: ProblemFilters)` R · `edit(id, ProblemEdit)` W · `get(id)` R · `reply(id)` R · `statuses()` R |
| `tasks` (6) | `list/iter(filters)` R · `get(id)` R · `edit(id, TaskEdit)` W · `create(TaskCreate)` W · `types()` R · `statuses()` R |
| `tags` (2) | `list(set_id)` R · `sets(object_id)` R |

Итого 73: 46 R, 26 W, 1 D. Плюс `health()`, не описанный в спецификации; в MCP он не публикуется.

Справочники (`statuses`, `types`, `stages` и т. п.) кешируются в клиенте с TTL 1 час. Кеш можно отключить параметром `cache_ttl=0`.

## 5. MCP‑сервер (`tehzor/mcp/`)

- Официальный Python SDK `mcp` (FastMCP).
- Транспорты: `stdio` по умолчанию (`tehzor-mcp`) и `--transport streamable-http --port 8000`.
- Конфигурация через env: `TEHZOR_API_KEY` (обязателен), `TEHZOR_USER_ID`, `TEHZOR_BASE_URL`, `TEHZOR_PROXY`, `TEHZOR_SSL_VERIFY` (по умолчанию 1), `TEHZOR_MAX_CONCURRENCY`.
- `lifespan` создаёт один `TehzorClient` на процесс и закрывает его при остановке.

**Генерация инструментов из реестра**, чтобы не писать 73 обработчика вручную:
```python
for op in registry.all():
    mcp.add_tool(make_tool(op), name=op.tool_name, description=op.description,
                 annotations=ToolAnnotations(readOnlyHint=op.read_only,
                                             destructiveHint=op.kind in ("W", "D"),
                                             idempotentHint=op.idempotent))
```
`make_tool` строит функцию с сигнатурой метода ресурса. Параметры‑модели (`ProblemFilters`, `TaskCreate`…) FastMCP превращает в JSON Schema автоматически.

**Адаптация под LLM:**
- Описание инструмента = `description` из спецификации плюс подсказки: какие id подходят (внешний или внутренний), где взять допустимые значения (например, «статусы — инструмент `problems_statuses`»).
- Ответы — компактный JSON: `exclude_none`, даты в ISO 8601 (UTC).
- Для списков используется обёртка `{"items": [...], "count": n, "next_offset": k | null, "truncated": bool}`. По умолчанию `limit=50`, жёсткий потолок 500. Агент листает сам, через `offset`.
- Параметр `fields` (если эндпоинт его поддерживает) и клиентский параметр `include` позволяют сократить ответ.
- Ошибки превращаются в `ToolError` с понятным текстом на русском («Нарушение не найдено (404) для id=…», «Нет доступа (403)…»). Тело ответа обрезается до 1 КБ.
- **Ресурсы MCP** — справочники, которые агент читает без вызова инструментов: `tehzor://stages`, `tehzor://processes`, `tehzor://problem-statuses`, `tehzor://task-statuses`, `tehzor://task-types`, `tehzor://work-acceptance-statuses`, `tehzor://space-types`…
- **Промпты MCP** (по желанию): «Сводка нарушений по объекту», «Статус приёмки квартиры», «Просроченные нарушения подрядчика».
- **Агрегирующие инструменты** поверх 73 операций, чтобы агенту не приходилось делать десятки вызовов:
  - `problems_search(objects, statuses, modified_from, modified_to, limit)` — автопагинация до `limit` записей;
  - `space_overview(space_id)` — помещение, статус, счётчики, передачи и гарантийные заявления.

## 6. Тесты

- `tests/unit/test_transport.py`:
  - маппинг 400/401/403/404/409/429/5xx в исключения;
  - ретраи с учётом `Retry-After`;
  - таймаут;
  - 200 и 201 считаются успехом;
  - ошибка одной задачи в `TaskGroup` не закрывает сессию;
  - `ssl` и `proxy` передаются в запрос;
  - ключ не попадает в логи.
- `tests/unit/test_operations.py` — **параметризован реестром**. Для каждой из 73 операций он:
  1. мокает `aioresponses` на `method + path` с фикстурой `tests/fixtures/<operationId>.json`;
  2. вызывает метод ресурса;
  3. проверяет тип результата, URL, query‑параметры и JSON‑тело запроса (camelCase, без `None`).
- `tests/unit/test_models.py`: `Timestamp`; алиасы `areaBTI`/`_id`; `extra="allow"` (новые поля не ломают разбор); неизвестный enum не ломает разбор; регресс на `SpaceEdit(area_bti=…)`.
- `tests/unit/test_coverage.py`: множество `(method, path)` из `docs/openapi.json` совпадает с реестром.
- `tests/unit/test_mcp.py`: через in‑memory клиент `mcp` проверяется, что зарегистрировано 73 инструмента и у каждого корректная JSON Schema; вызов `problems_get` на моке; формат ошибки; усечение списка.
- `tests/integration/` (`-m integration`, нужен `TEHZOR_API_KEY`): только чтение — `objects.stages`, `problems.list(limit=1)`, `spaces.list(limit=1)`, `tasks.list(limit=1)`.
- Фикстуры: на старте — синтетические, по схемам спецификации. Затем `scripts/record_fixtures.py` заменяет их реальными ответами с обезличиванием ФИО, email, телефонов. Для этого нужен доступ к `api.tehzor.ru` (с машины пользователя или после разрешения домена в настройках облачной сессии).
- Цель покрытия: ≥ 90% по `tehzor/` (`pytest --cov`).

## 7. Этапы и сроки (1 разработчик)

| Этап | Содержание | Оценка |
|---|---|---|
| 0. Каркас | Ветка, `pyproject.toml`, ruff + mypy (strict для `tehzor/`), pytest, GitHub Actions (3.10–3.13), `docs/openapi.json`, удаление `config.py`/`utils.py`/`publish.py`/`setup.py`, `.env.example` | 1 день |
| 1. Ядро | `_transport`, `errors`, `_pagination`, `_registry`, `types.Timestamp`, `models/_base`, `TehzorClient` + unit‑тесты транспорта | 3 дня |
| 2. Модели | Все DTO по доменам, enum‑ы, `check_spec_drift.py` | 4 дня |
| 3a. Ресурсы: текущий функционал | `problems`, `spaces`, `work_acceptances`, `warranty_claims`, `space_owners` (36 операций) + фикстуры и тесты | 4 дня |
| 3b. Ресурсы: остальное | `objects`, `categories`, `check_lists`, `checks`, `comments`, `internal_acceptances`, `owner_acceptances`, `tasks`, `tags` (37 операций) + тесты; `test_coverage` становится зелёным | 4 дня |
| 4. MCP | `tehzor/mcp`: автогенерация инструментов, ресурсы‑справочники, агрегирующие инструменты, форматирование ответов и ошибок, stdio и HTTP, тесты | 4 дня |
| 5. Реальные данные | Запись фикстур на боевом API, правка расхождений (200/201, `attachments`, формат дат фильтра), интеграционные тесты | 2 дня |
| 6. Релиз 0.2.0 | README (клиент + MCP: конфиги для Claude Desktop и Claude Code), гайд миграции с 0.1.x, переписанные `examples/`, CHANGELOG, тег `v0.2.0`, публикация через PyPI Trusted Publishing из GitHub Actions | 2 дня |

Итого около 24 рабочих дней, это 4–5 недель. Этапы 3a и 3b можно распараллелить между двумя людьми, если интерфейс ядра зафиксирован.

Порядок коммитов: каждый этап — отдельный PR в `develop`. Работа идёт в ветке `claude/hopeful-einstein-ehtyi0`, промежуточные коммиты по ресурсам.

## 8. Ключевые примеры «было → стало»

```python
# было
thz = await TehzorAPI.create(api_key=KEY, user_id=UID)
async for p in thz.get_problems(limit=50000, filter=ProblemFilter(objects=[obj])): ...
await thz.update_spaces(id, SpaceUpdate(area_bti=55.1).model_dump_json(by_alias=True))  # area_bti терялся
await thz.session_close()

# стало
async with TehzorClient(api_key=KEY, user_id=UID) as thz:
    async for p in thz.problems.iter(filters=ProblemFilters(objects=[obj], statuses=["waiting"])):
        ...
    await thz.spaces.edit(space_id, SpaceEdit(area_bti=55.1, type_decoration=decor_id))
    created = await thz.problems.create(ProblemCreate(object_id=obj, category_id=cat,
                                                      stage=Stage.TRANSFER, process_id=Process.UNITS_HANDOVER,
                                                      links=ProblemLinks(space_id=sp), description="…"))
```

Подключение MCP (Claude Code):
```bash
claude mcp add tehzor --env TEHZOR_API_KEY=... -- uvx --from "tehzor[mcp]" tehzor-mcp
```

## 9. Verification

1. `ruff check . && mypy tehzor` — без ошибок.
2. `pytest tests/unit --cov=tehzor` — зелёный, покрытие ≥ 90%, `test_coverage.py` подтверждает 73 из 73.
3. `python scripts/check_spec_drift.py docs/openapi.json` — расхождений нет, кроме документированных в §3.
4. `pytest -m integration` с реальным ключом (на машине пользователя или после разрешения `api.tehzor.ru`) — чтение работает.
5. MCP:
   - `npx @modelcontextprotocol/inspector tehzor-mcp`: видно 73 инструмента и ресурсы‑справочники; `problems_list` с `limit=5` возвращает `items` и `next_offset`; запрос с неверным id даёт понятную `ToolError`.
   - Сквозная проверка в Claude Code: «покажи 5 последних нарушений по объекту X и их статусы».
6. `python -m build && twine check dist/*` — wheel не содержит `tests/`, `examples/`, `scripts/`.

## 10. Что понадобится от пользователя по ходу работы

- Тестовый API‑ключ и объект, на котором безопасно создавать и удалять сущности при проверке write‑операций. Без них write‑операции проверяются только на моках.
- Доступ к `api.tehzor.ru` для записи фикстур (этап 5).
