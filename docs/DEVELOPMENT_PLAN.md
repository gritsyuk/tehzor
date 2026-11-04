# План: переписать `tehzor` под полный Public API v1.44.0 и MCP-сервер для LLM‑агента

## Context

Текущая обёртка (`tehzor/api.py`, 0.1.3) покрывает 13 из 73 операций Tehzor Public API v1.44.0. Часть моделей не совпадает со спецификацией: `WorkAcceptances` унаследована от `Problem` и требует несуществующее `acceptanceDate`, `typeDecoration` объявлен строкой, хотя это объект. Есть и системные дефекты: SSL выключен, при ошибке закрывается сессия, ответы проверяются через `assert`, пагинации нет, тестов без сети нет.

Цель — библиотека с полным соответствием 73 операциям и MCP‑сервер поверх неё, через который LLM‑агент работает с «Техзором».

Принятые решения:
- **Ломаем совместимость, выпускаем 0.2.0.** Старый `TehzorAPI` удаляется, в README будет гайд миграции.
- **MCP‑сервер живёт в этом же репозитории**: модуль `tehzor/mcp/`, extra `tehzor[mcp]`, команда `tehzor-mcp`.
- **Агенту доступны все 73 операции**, но каждая изменяющая операция (создание, изменение, смена статуса, привязка, удаление — 26 W + 1 D) выполняется **только после подтверждения человеком** (см. §5a).
- **Создание и удаление на реальном API в рамках разработки не проверяем.** Изменяющие операции в библиотеке и в MCP проверяются только на заглушках (`aioresponses` / фейковый транспорт). Живые проверки строго только на чтение, и это обеспечено технически, а не договорённостью (см. §6a).
- **Фактические ответы API важнее спецификации.** `docs/openapi.json` расходится с реальностью, поэтому для каждого читающего эндпоинта есть автоматический контрактный тест: он вызывает живое API и сверяет ответ с pydantic‑моделью и со спецификацией (см. §6a).

Источники: OpenAPI v1.44.0 (пользователь прислал его, он сохраняется в `docs/openapi.json`) задаёт стартовые модели, а **контрактные тесты на живом API** определяют их окончательный вид.

API‑ключ даёт пользователь. Ключ никогда не попадает в репозиторий, в логи и в фикстуры. Локально он лежит в `.env` (файл в `.gitignore`), в CI — в GitHub Secret `TEHZOR_API_KEY`, в облачной сессии — в переменных окружения. Чтобы облачная сессия могла ходить в API, домен `api.tehzor.ru` нужно добавить в её сетевые настройки.

---

## 1. Целевая структура пакета

```
pyproject.toml                # hatchling; deps: aiohttp>=3.9,<4; pydantic>=2.6,<3
                              # extras: mcp = ["mcp>=1.2,<2"]; dev = [pytest, pytest-asyncio, aioresponses, ruff, mypy]
docs/openapi.json             # спецификация v1.44.0
scripts/check_spec_drift.py   # сверка моделей и реестра операций с openapi.json
scripts/contract_report.py    # отчёт «факт vs модель vs спецификация» по 46 читающим эндпоинтам
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
    confirm.py                # превью, confirmation_id, elicitation, confirm_operation (§5a)
    audit.py                  # JSONL-журнал изменяющих операций
    __main__.py               # python -m tehzor.mcp
tests/
  unit/                       # aioresponses, без сети
  fixtures/                   # JSON-ответы по operationId (обезличенные)
  contract/                   # @pytest.mark.contract: живое API, только чтение (§6a)
    seeds.toml  known_extras.toml  snapshots/
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

## 5a. Контроль человека над изменяющими операциями

Правило распространяется на все 27 изменяющих операций (`kind` W или D в реестре): create, edit, set‑status/resolution, bind/unbind, delete, `work_acceptances.create_many`. Изменение данных так же необратимо для бизнеса, как создание, поэтому edit тоже здесь.

**Уровни защиты в MCP (все включены по умолчанию):**
1. **Запись выключена, пока её явно не включили.** Без `TEHZOR_MCP_ALLOW_WRITE=1` изменяющие инструменты регистрируются, но любой вызов возвращает `ToolError`: «запись отключена администратором». Агент видит, что операция существует, но выполнить её не может.
2. **Подтверждение человеком на каждый вызов — двухшаговый протокол:**
   - Агент вызывает, например, `problems_create(...)`. Сервер **ничего не отправляет в API**: он проверяет вход по pydantic‑модели и возвращает превью — метод, путь, итоговое JSON‑тело, человекочитаемое описание («Создать нарушение в объекте X, помещение Y, вид работ Z») — и одноразовый `confirmation_id` (срок жизни 10 минут, привязан к хэшу тела).
   - Если клиент поддерживает MCP elicitation, сервер сам запрашивает у человека «Подтвердить / Отклонить» через `ctx.elicit(...)`. Только после ответа «Подтвердить» запрос уходит в API.
   - Если клиент elicitation не поддерживает, нужен отдельный вызов `confirm_operation(confirmation_id)`. Его аннотация `destructiveHint=true`, а в описании прямо сказано: «вызывать только после явного согласия пользователя в чате». Клиенты (Claude Code, Claude Desktop) по этой аннотации запрашивают разрешение у человека.
   - Подмена данных между превью и подтверждением невозможна: выполняется ровно то тело, хэш которого сохранён вместе с `confirmation_id`.
3. **Аннотации** `readOnlyHint` / `destructiveHint` / `idempotentHint` на всех инструментах, чтобы клиент сам показывал запрос разрешения.
4. **Журнал аудита.** Каждое превью, подтверждение, отказ и результат пишется в JSONL‑файл (`TEHZOR_MCP_AUDIT_LOG`, по умолчанию `~/.tehzor-mcp/audit.jsonl`): время, инструмент, тело (персональные данные маскируются), `confirmation_id`, статус ответа API. Ключ в журнал не попадает.
5. **Опциональный allowlist**: `TEHZOR_MCP_WRITE_TOOLS=problems_create,comments_create` разрешает запись только перечисленными инструментами.

**В библиотеке** человек — это программист, поэтому превью и подтверждения нет. Но есть:
- `TehzorClient(read_only=True)`: любой вызов W или D бросает `ReadOnlyError` ещё до сетевого запроса. Этот режим используют контрактные тесты (§6a) и MCP, пока запись выключена.
- `dry_run=True` у изменяющих методов: вернуть подготовленный запрос (`PreparedRequest`: метод, путь, тело) без отправки. MCP строит своё превью на этом же механизме.

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
- **Изменяющие операции (27 шт.) тестируются только на заглушках**, и в библиотеке, и в MCP. Проверяется:
  - URL, метод, query и JSON‑тело (camelCase, без `None`);
  - разбор ответа: фикстура строится по схеме спецификации, а где ответ возвращает ту же сущность, что и чтение (например, `GetProblemDto`), — по реальному ответу соответствующего GET;
  - обработка 400/403/404/409;
  - в MCP: без `ALLOW_WRITE` запрос не уходит; без подтверждения запрос не уходит; после подтверждения уходит ровно подтверждённое тело; истёкший или чужой `confirmation_id` отклоняется; запись в журнал аудита.
  Контроль такой: тестовая заглушка падает на любом неожиданном HTTP‑вызове (`aioresponses` без `passthrough`), поэтому случайно сходить в сеть из unit‑тестов нельзя.
- Цель покрытия: ≥ 90% по `tehzor/` (`pytest --cov`).

## 6a. Контрактные тесты: что эндпоинт возвращает на самом деле

Задача — для каждого из 46 читающих эндпоинтов автоматически и в любой момент проверить, что реальный ответ соответствует типам pydantic‑моделей, и увидеть, чем он отличается от спецификации.

**Расположение:** `tests/contract/`, маркер `@pytest.mark.contract`. Запуск: `pytest -m contract` (нужны `TEHZOR_API_KEY` и доступ к `api.tehzor.ru`). По умолчанию в `pytest` эти тесты не запускаются.

**Безопасность — только чтение, гарантировано кодом:**
- Тесты создают клиент с `read_only=True`; любая W/D‑операция бросает `ReadOnlyError` до сети.
- Дополнительно транспорт в контрактном режиме разрешает только операции из реестра с `kind == "R"`. Это проверяется по `method + path`, а не по HTTP‑методу, потому что в Техзоре чтение списков идёт через `POST .../get-*`.
- Тест `test_contract_is_read_only` проходит по реестру и падает, если в контрактный набор попала W/D‑операция.

**Как выбираются id для детальных эндпоинтов** — цепочка от списков, без ручного ввода:
`objects` ← `problems.list(limit=N)` → `problems.get(id)`, `problems.reply(id)`; `spaces.list` → `spaces.get`, `get_status`, `meters`, `owner_acceptances`, `warranty_claims` → `warranty_claims.get`, `warranty_claims.problems`; `work_acceptances.list` → `get`; `internal_acceptances.list` → `get`, `problems`; `tasks.list` → `get`; `comments.list` → `get`; `categories.sets` → `categories.list(set_id)`; `tags.sets` → `tags.list`; `check_lists.list` → `get`, `get_status`, `get_item_status`; `owner_acceptances` берутся из `spaces.owner_acceptances`; `checks.get` — по `links.checkId` из нарушений.
Где цепочка не даёт id, его можно задать в `tests/contract/seeds.toml` (`OBJECT_ID`, `SPACE_ID`…), или через env. Если id так и не найден, тест помечается `skip` с причиной, а не «зелёным».

**Что проверяет каждый тест** (выборка из N записей, по умолчанию 20 на список):
1. HTTP‑статус и `Content-Type`.
2. **Валидация моделью в строгом режиме.** Используется `TehzorModel` с `extra="allow"`, и после разбора рекурсивно собирается `model_extra`. Тест падает, если:
   - модель не разобрала ответ (`ValidationError`: неверный тип, нет обязательного поля);
   - в ответе есть **поля, не описанные в модели** (недокументированные или переименованные). Их можно один раз осознанно занести в allowlist `tests/contract/known_extras.toml`.
3. **Сверка со спецификацией** (`docs/openapi.json`): какие поля пришли, но не описаны в схеме; какие `required` по спецификации, но отсутствуют или `null`; где тип в ответе отличается от типа в схеме (строка вместо объекта, массив объектов вместо строк). Это не провал теста, а отчёт: спецификация заведомо неточная.
4. **Снимок фактической схемы.** Из реальных ответов выводится схема: поле → множество наблюдаемых типов, доля `null`, примеры значений enum. Она сохраняется в `tests/contract/snapshots/<operationId>.schema.json`. Сами данные не сохраняются. При следующем запуске тест сравнивает снимки и сообщает о дрейфе API (появилось или пропало поле, сменился тип).

**Отчёт.** `scripts/contract_report.py` (или `pytest -m contract --contract-report=reports/contract.md`) пишет Markdown и JSON. В нём таблица по 46 эндпоинтам — «модель ОК / расхождения с моделью / расхождения со спецификацией / дрейф с прошлого запуска» — и детали по каждому полю. Отчёт служит рабочим списком для правки моделей.

**Фикстуры для unit‑тестов** записываются тем же механизмом (`--record-fixtures`). Персональные данные обезличиваются: ФИО, email, телефоны, имена собственников заменяются на детерминированные заглушки, id сохраняются. Записываются только ответы читающих эндпоинтов.

**Регулярность:**
- Вручную в любой момент: `pytest -m contract`.
- По расписанию в GitHub Actions раз в сутки (job `contract`, секрет `TEHZOR_API_KEY`). При любом расхождении job падает и прикладывает отчёт как артефакт.
- В облачной сессии Claude — после того как пользователь передаст ключ через переменные окружения и разрешит домен `api.tehzor.ru`.

## 7. Этапы и сроки (1 разработчик)

| Этап | Содержание | Оценка |
|---|---|---|
| 0. Каркас | Ветка, `pyproject.toml`, ruff + mypy (strict для `tehzor/`), pytest, GitHub Actions (3.10–3.13), `docs/openapi.json`, удаление `config.py`/`utils.py`/`publish.py`/`setup.py`, `.env.example` | 1 день |
| 1. Ядро | `_transport`, `errors`, `_pagination`, `_registry`, `types.Timestamp`, `models/_base`, `TehzorClient` + unit‑тесты транспорта | 3 дня |
| 2. Модели (черновик) | Все DTO по доменам из спецификации, enum‑ы, `check_spec_drift.py` | 3 дня |
| 3. Контрактные тесты | `read_only`‑режим, цепочка id, проверка моделью + `model_extra`, сверка со спецификацией, снимки, отчёт, запись обезличенных фикстур. **Первый прогон на живом API → правка моделей по факту** (200/201, `attachments`, `typeDecoration`, формат дат фильтра и всё, что найдёт отчёт). Nightly‑job в CI | 4 дня |
| 4a. Ресурсы: текущий функционал | `problems`, `spaces`, `work_acceptances`, `warranty_claims`, `space_owners` (36 операций) + unit‑тесты; запись — только заглушки | 4 дня |
| 4b. Ресурсы: остальное | `objects`, `categories`, `check_lists`, `checks`, `comments`, `internal_acceptances`, `owner_acceptances`, `tasks`, `tags` (37 операций) + unit‑тесты; `test_coverage` и контракт по всем 46 R становятся зелёными | 4 дня |
| 5. MCP | Автогенерация инструментов, ресурсы‑справочники, агрегирующие инструменты, форматирование ответов и ошибок, stdio и HTTP; **контроль записи (§5a)**: флаг `ALLOW_WRITE`, превью + `confirmation_id`, elicitation, `confirm_operation`, журнал аудита, allowlist; тесты на заглушках | 5 дней |
| 6. Релиз 0.2.0 | README (клиент, MCP с конфигами для Claude Desktop и Claude Code, отдельный раздел «Запись данных и подтверждение»), гайд миграции с 0.1.x, переписанные `examples/`, CHANGELOG, тег `v0.2.0`, PyPI Trusted Publishing | 2 дня |

Итого около 26 рабочих дней, это 5 недель. Контрактные тесты стоят **до** ресурсов: модели правятся по реальным ответам раньше, чем на них опирается остальной код. На этапе 3 контрактный раннер вызывает API напрямую через `Transport` по метаданным реестра (метод, путь, модель ответа). Когда на этапе 4 появятся методы ресурсов, тесты переключатся на них. Этапы 4a и 4b можно распараллелить между двумя людьми, если интерфейс ядра зафиксирован.

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
4. `pytest -m contract --contract-report=reports/contract.md` с ключом пользователя: по всем 46 читающим эндпоинтам модель разбирает реальный ответ без лишних полей (кроме allowlist); отчёт показывает расхождения со спецификацией. В журнале транспорта нет ни одного вызова W/D‑операции.
5. MCP (только чтение на живом API, запись — на заглушках):
   - `npx @modelcontextprotocol/inspector tehzor-mcp`: видно 73 инструмента и ресурсы‑справочники; `problems_list` с `limit=5` возвращает `items` и `next_offset`; запрос с неверным id даёт понятную `ToolError`.
   - Без `TEHZOR_MCP_ALLOW_WRITE` вызов `problems_create` отказывает. С флагом, но на фейковом транспорте, он возвращает превью и `confirmation_id`; после `confirm_operation` фейковый транспорт получает ровно показанное тело; в `audit.jsonl` появляются записи.
   - Сквозная проверка в Claude Code на чтение: «покажи 5 последних нарушений по объекту X и их статусы».
6. `python -m build && twine check dist/*` — wheel не содержит `tests/`, `examples/`, `scripts/`.

## 10. Что понадобится от пользователя по ходу работы

- **API‑ключ.** Передавать через переменную окружения облачной сессии или GitHub Secret `TEHZOR_API_KEY`, а не текстом в чат: из чата ключ попадает в историю разговора. Ключ используется только для чтения.
- **Доступ к `api.tehzor.ru`** в сетевых настройках сессии — к этапу 3.
- По желанию: один‑два id объектов и помещений с «богатыми» данными для `seeds.toml`, чтобы контрактные тесты прошли по редким эндпоинтам (чек‑листы, передачи, проверки).
- Тестовый объект для записи **не нужен**: создание, изменение и удаление на живом API в рамках разработки не выполняются. Если когда‑нибудь понадобится ручная приёмка записи на реальных данных, её проводит человек через MCP с подтверждением каждой операции (§5a). Автоматизированные тесты так никогда не делают.
