# Факты о Tehzor Public API

> **`docs/openapi.json` — не источник истины.** Это заявление разработчика API о доступных
> методах и о том, как они *должны* выглядеть. Истина — фактические ответы API.
> Модели библиотеки строятся по фактам из этого файла и по контрактным тестам
> (`pytest -m contract`), а не по спецификации. Если тест показал расхождение, правится модель.
>
> Кроме того, API может иметь методы, не описанные в `openapi.json` (см. «Недокументированные методы»).

Проверка: 2026-11-04, спецификация v1.44.0 (`https://api.tehzor.ru/docs-json`, 73 операции).
Только читающие запросы. Значения полей не сохранялись, только названия и типы.

## Производительность и ограничения сервера

| Запрос | Результат |
|---|---|
| `GET /stages` | 200 |
| `POST /problems/get-problems?limit=1` без фильтра | **502 примерно через 31 с** (таймаут шлюза около 30 с) |
| `POST /problems/get-problems?limit=1` с `{"objects": [<id объекта>]}` | 200 за 1,2 с |
| `GET /spaces/{id}` | 200 за 0,2 с |
| `GET /objects/{id}` | 200 за 1,2 с |
| `POST /problems/get-problems?limit=100` с фильтром по объекту (крупный объект) | 200 за **14,9 с** — половина лимита шлюза |

Вывод: списочные запросы делаются только с фильтром по объекту. 502 после долгого
ожидания означает «запрос слишком тяжёлый», а не «повторите». Время ответа растёт
с `limit` (100 записей ≈ 15 с), поэтому размер страницы по умолчанию — **50**, а не 100.

## Форматы id

| Сущность | Формат |
|---|---|
| Объект `id` | UUID (новая архитектура) |
| Объект `externalId` | 24 hex (старый id объекта) |
| Нарушение, помещение, вид работ, проверка, статус помещения | 24 hex (пока) |

Вывод: все id в моделях — обычная `str` без проверки формата. API переводит сущности
на новые id постепенно.

## Объект (`GetObjectDto`)

| Поле | Спецификация | Факт |
|---|---|---|
| `customFields` | обязательный объект | `null` |
| остальные (`id`, `externalId`, `name`, `fullName`, `parentId`, `companyId`, `stage`, `city`, `address`) | обязательные строки | строки (совпадает) |

## Нарушение (`GetProblemDto`)

| Поле | Спецификация | Факт |
|---|---|---|
| `attachments` | `string[]` | `[{id, preview: {...}, full: {...}}]` |
| `inspectors` | `UserDto[]` | `[{id}]` |
| `watchers` | `UserDto[]` | `[str]` (id пользователей) |
| `processId` | нет | есть, например `operational-control` |
| `color` у `createdBy`, `modifiedBy`, `performers*` | нет | есть |
| `links` | 12 обязательных ключей | только заполненные: `{checkId}`; на стадии передачи `{spaceId, ownerAcceptanceId}`; на гарантии `{spaceId, warrantyClaimId}` |
| `space`, `plan`, `actualFixDate`, `displayLocation` | — | приходят, если заполнены (выборка из 100 нарушений) |
| `location`, `plan`, `floor`, `plannedFixDate`, `actualFixDate`, `displayLocation`… | обязательные | отсутствуют, если не заполнены |
| `createdAt`, `modifiedAt` | number | int, миллисекунды (13 цифр) |
| `stage` | enum | `building` (совпадает) |
| `status` | `{id, name}` | совпадает, id строковый (`verification`) |

## Помещение (`GetSpaceDto`)

| Поле | Спецификация | Факт |
|---|---|---|
| `createdBy`, `modifiedBy` | `UserDto` | есть `employers: []`, нет `color` |
| `customFields` | обязательное | отсутствует |
| `typeDecoration`, `plannedArea`, `areaBTI`… | — | не пришли (пустые поля сервер не отдаёт). **Формат `typeDecoration` не подтверждён** |
| `status` | `{id, name, stage}` | совпадает |
| `type` | `{id, name, singularName}` | совпадает |

## Недокументированные методы

| Метод | Статус |
|---|---|
| `GET /health/readiness` | 200, в `openapi.json` отсутствует |

## Итог контрактных тестов (2026-11-04)

`pytest -m contract` на трёх объектах (один со всеми стадиями) и помещении с прибором учёта:
**53 теста пройдено, пропусков нет**. Все 49 читающих операций и `/health/readiness` разобраны моделями
**без неописанных полей**.

Расхождений со спецификацией: **236** (информационно, спецификация не источник истины):

| Вид | Кол-во | Примеры |
|---|---|---|
| spec называет поле обязательным, а оно приходит не всегда | 164 | почти все поля нарушений, задач, приёмок; `customFields` |
| поля нет в spec | 60 | `processId`, `color`, `employers`, `reopenedTimes`, `registrationDate`, `createdFromEntity`, `shared`, `checkListName`… |
| другой тип | 12 | `attachments[]`: объект, а не строка; `watchers[]`: строка, а не объект; `/contract-forms`, `/space-types-decorations`, `/space-statuses`: список, а не объект |

Полный отчёт по полям: `TEHZOR_CONTRACT_REPORT=reports/contract pytest -m contract` → `reports/contract.md`.
Снимки фактических схем (только поля и типы, без значений): `tests/contract/snapshots/`.

## Подтверждённые особенности

| Эндпоинт / поле | Факт |
|---|---|
| `Space.typeDecoration` | объект `{id, name}` (подтверждено); в запросе изменения передаётся id |
| `GET /spaces/{id}/meters` | 404 «приборы не найдены», если приборов нет (400 — нет помещения); клиент возвращает `[]`. Прибор: `{id, type{id,name,measureUnit}, serialNumber, description, consumptions[{id, value, tariff, createdAt, createdBy, modifiedAt}], createdAt, createdBy, modifiedAt}` — `modifiedBy` нет (spec: обязателен) |
| `GET /spaces/{id}/owner-acceptances` | `status {id, name}` есть не у всех передач |
| `GET /problems/{id}/reply` | 404, если официального ответа нет; клиент возвращает `None`. Ответ — комментарий (`ancestors`, `number`, `official`) |
| `GET /owner-acceptances/{id}` | `resolution` = `{id, name}` (spec: `_id`); `status`, `spaceOwner` не встречались; есть `localId` |
| `GET /warranty-claims/{id}` | `status` — строка; в `/spaces/{id}/warranty-claims` — объект `{id, name}`; есть `registrationDate` |
| `GET /work-acceptances/{id}` | нет `acceptors` (есть в списке), есть `*Leader`; пользователи только `{id, fullName}` |
| `GET /warranty-claims/{id}/problems` | сокращённая форма нарушения: id, number, status, description, plannedFixDate, categoryId |
| `GET /tasks/{id}` | у пользователей нет `fullName`; есть `link` |
| `Comment.number` | бывает `null` |
| `GET /check-lists/item-status` | есть `checkListName` (нет в spec) |
| `/health/readiness` | `{status, info, error, details}` |

## Запись: проверка в песочнице (только созданные в прогоне сущности)

Уровень 1, 2026-11-04 (`python -m tests.sandbox.level1_space_owners --execute`): собственник создан → изменён →
найден → удалён. После прогона ничего не осталось.

| Операция | Факт |
|---|---|
| `POST /space-owners` | 2xx, ответ `{id, name, comment, companyId, spaces}`. spec: ответ без `id` — на деле `id` есть; `companyId` нет в spec |
| `POST /space-owners/{id}` с одним `comment` | частичное обновление: в ответе те же поля, `id` прежний |
| `POST /space-owners/get-or-create` с тем же `name` | возвращает существующего собственника (тот же `id`), дубль не создаётся |
| `DELETE /space-owners/{id}/delete` | ответ `{success}` |

Уровень 2, 2026-11-04 (`TEHZOR_SANDBOX_SPACE_ID=… python -m tests.sandbox.level2_bind_space --execute`):
собственник создан → привязан к тестовому помещению → отвязан → удалён. После прогона ничего не осталось.

| Операция | Факт |
|---|---|
| `POST /space-owners/{ownerId}/bind/{spaceId}` с `{unbindExistingOwners: false}` | ответ — собственник, `spaces` содержит помещение |
| `POST /space-owners/{ownerId}/unbind/{spaceId}` без тела | ответ — собственник, `spaces` пуст |

`unbindExistingOwners: true` отвязал бы существующих собственников помещения — в песочнице запрещён и не проверялся.

Уровень 3, нарушение на стадии строительства, 2026-11-04 (`python -m tests.sandbox.level3 <шаг> --execute`,
тестовый объект и помещение заданы пользователем). Нарушение и комментарий **остались** в объекте
(удаления в API нет), нарушение закрыто, в описании метка `[TEST tehzor-python 2026-11-04]`.

| Операция | Факт |
|---|---|
| `POST /problems` (без исполнителей и наблюдателей) | 2xx, ответ — полное нарушение, статус `waiting`. **Сервер сам назначил исполнителей (2), рабочую группу с руководителем и наблюдателя (1)** — по настройкам объекта; назначенные могут получить уведомление |
| `POST /problems/{id}` с `description` и `plannedFixDate` | **частичное обновление**: вид работ, стадия, процесс, исполнители, наблюдатели сохранились |
| `POST /comments` (`problem-comment`, `official: false`) | 2xx; в ответе нет `number` и `createdBy` |
| `POST /problems/{id}` с `{status: closed}` из `waiting` | разрешено напрямую, без промежуточных статусов; появляется `actualFixDate` |

Уровень 3, группа C — тестовое помещение, 2026-11-04: поле и статус изменены и **возвращены по снимку**;
итоговое сравнение с исходным состоянием — отличий нет (кроме `modifiedAt`/`modifiedBy`).

| Операция | Факт |
|---|---|
| `POST /spaces/{id}` с `{plannedArea}` | частичное обновление: изменилось только переданное поле |
| `POST /spaces/{id}/set-status/{statusId}` | смена «Выявлены нарушения» → «Не осмотрено» (одна стадия) и обратно принята без 409; ручной возврат не перезаписывается автоматически |

Ограничение обёртки: `SpaceEdit` не отправляет `None`, поэтому очистить поле (вернуть в «пусто») через `edit` нельзя.

В API нет удаления для остальных сущностей (нарушения, задачи, комментарии, приёмки, передачи, гарантия,
виды работ, проверки): полностью обратимо через API можно проверить только собственников.

## Не проверено

- Формат дат `modifiedAtFrom/To` в фильтре нарушений (spec: строка).
- Изменяющие операции, кроме 6 операций собственников (уровни 1–2): только на заглушках. Создание необратимых сущностей (уровень 3) — только после отдельного решения пользователя и с тестовым объектом/помещением.
- Код ответа (200 или 201) у `POST /spaces/{id}` и `POST /space-owners`: без записи проверить нельзя, клиент принимает любой 2xx.
