# Миграция с 0.1.x на 0.2.0

0.2.0 — новый интерфейс. Старый `TehzorAPI` удалён. Ниже соответствие старых вызовов новым.

## Клиент и сессия

```python
# 0.1.x
thz = await TehzorAPI.create(api_key=KEY, user_id=UID, verify_ssl=False)
...
await thz.session_close()

# 0.2.0
from tehzor import TehzorClient

async with TehzorClient(api_key=KEY, user_id=UID) as thz:   # SSL проверяется по умолчанию
    ...
```

`api_key` можно не передавать — берётся `TEHZOR_API_KEY`. `limit_threads` → `max_concurrency` (по умолчанию 5)
плюс `rate_limit` (5 запросов/с). `proxy=` остался; также учитываются `HTTPS_PROXY`/`NO_PROXY`.

## Методы

| 0.1.x | 0.2.0 |
|---|---|
| `get_problem(id)` | `problems.get(problem_id)` |
| `get_problems(limit=50000, filter=ProblemFilter(objects=[…]))` | `problems.iter(ProblemFilters(objects=[…]))` — постранично; одна страница — `problems.list(..., limit, offset)` |
| `update_problem(id, data: dict)` | `problems.edit(problem_id, ProblemEdit(...))` |
| — | `problems.create(ProblemCreate(...))`, `problems.reply(id)`, `problems.statuses()` |
| `get_space(id)` | `spaces.get(space_id)` |
| `get_spaces(filter=SpacesFilter(spaces=[…]))` (возвращал `dict`) | `spaces.iter(SpaceFilters(objects=[…]))` → модели `Space` |
| `update_spaces(id, data_json_str)` | `spaces.edit(space_id, SpaceEdit(area_bti=..., type_decoration=...))` |
| `get_space_meters(id)` | `spaces.meters(space_id)` (нет приборов → `[]`, а не 404) |
| `get_space_types_decorations()` | `spaces.decoration_sets()` |
| `get_contract_forms()` | `spaces.contract_forms()` |
| `create_owners(data)` | `space_owners.create(SpaceOwnerCreate(...))` |
| `get_work_acceptance(id)` | `work_acceptances.get(work_acceptance_id)` |
| `get_work_acceptances(object_id, limit, offset)` | `work_acceptances.iter(object_id)` / `.list(object_id, limit=, offset=)` |
| `get_warranty_claims(id)` | `warranty_claims.get(warranty_claim_id)` |
| `health_check()` | `health()` |
| `CONSTRUCT_STAGES` | `objects.stages()`, `objects.processes()`, `tehzor.enums.Stage`, `ProcessId` |

## Модели (`tehzor.models.*`)

* Поля — snake_case, при разборе принимаются и camelCase-имена API. Все поля, кроме `id`, необязательные.
* Даты — `datetime` в UTC (в 0.1.x — наивное локальное время). В запросы уходят миллисекундами автоматически.
* `ProblemFilter` → `ProblemFilters` (добавлены `include_objects_children`, `statuses`, `modified_at_from/to`).
* `SpacesFilter` → `SpaceFilters` (добавлены `objects`, `include_objects_children`).
* `SpaceUpdate` → `SpaceEdit`; `area_bti`, `number_bti`, `floor_bti` теперь действительно отправляются.
* `WorkAcceptances` → `WorkAcceptance` (отдельная сущность; `acceptance_date` → `acceptance_interval_start/end`,
  `actual_acceptance_date`).
* `Space.type_decoration` — объект `{id, name}`; в `SpaceEdit.type_decoration` передаётся id.
* `Problem.attachments` — `Attachment(id, full, preview)`; `watchers` — список id.

## Ошибки

`TehzorAPIError` → иерархия `tehzor.TehzorError`: `NotFoundError` (404), `ForbiddenError` (403),
`BadRequestError` (400), `ConflictError` (409), `RateLimitError` (429), `ServerError` (5xx),
`QueryTooHeavyError`, `TehzorTimeoutError`, `ServiceUnavailableError`, `ReadOnlyError`. У HTTP-ошибок есть
`status`, `message`, `body`. Ошибка больше **не закрывает** сессию.

## Запись данных

```python
req = await thz.spaces.edit(space_id, SpaceEdit(area_bti=55.1), dry_run=True)   # ничего не отправляется
print(req.describe(), req.json)
space = await thz.spaces.edit(space_id, SpaceEdit(area_bti=55.1))               # отправка
```

`TehzorClient(read_only=True)` запрещает любые изменяющие операции до отправки запроса.
