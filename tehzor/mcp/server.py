"""MCP-сервер Tehzor для LLM-агентов.

* Инструменты генерируются из реестра операций библиотеки (все 73 операции API) — по сигнатурам методов
  ресурсов, поэтому схема параметров всегда совпадает с библиотекой.
* Чтение: компактный JSON, даты ISO 8601; списки — {items, count, offset, next_offset}; фильтр по объекту
  обязателен (без него API отвечает 502 через ~30 с).
* Запись (docs/DEVELOPMENT_PLAN.md, §5a): выключена без TEHZOR_MCP_ALLOW_WRITE=1; каждая изменяющая операция
  сначала возвращает превью и confirmation_id и выполняется только после подтверждения человеком
  (elicitation клиента или инструмент confirm_operation); отправляется ровно показанный запрос; журнал аудита.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
import typing
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, ValidationError

from .. import errors
from .._registry import REGISTRY, Operation
from .._transport import PreparedRequest
from ..client import TehzorClient
from ..insights import ObjectTree, ProjectsIndex
from .audit import AuditLog
from .config import Settings
from .confirm import PendingStore
from .insights_tools import register_insights

INSTRUCTIONS = """\
Инструменты Tehzor — системы строительного контроля и приёмки квартир.
- id объекта — UUID (например, из ссылки app.tehzor.ru/objects/<id>); id помещений, нарушений и др. — строки.
- Списки ВСЕГДА фильтруйте по объекту (objects / object_id): без фильтра сервер не справляется.
  Ответ списка: {items, count, offset, next_offset}; следующая страница — offset=next_offset.
- Справочники (статусы, типы, стадии) доступны как ресурсы tehzor://… и инструменты *_statuses / *_types.
- Все объекты компании деревом — objects_discover; по коду проекта — project_resolve (если заданы соответствия).
- Корпуса и секции сервер сам не учитывает: в problems_search / problems_summary / work_acceptances_search
  передавайте include_children=true. Сводка открытых/просроченных/критичных — problems_summary (правила внутри).
- Изменяющие инструменты (создание, изменение, смена статуса, удаление) НЕ выполняются сразу: они возвращают
  превью и confirmation_id. Покажите превью пользователю и вызывайте confirm_operation ТОЛЬКО после его явного
  согласия. Удаление необратимо; для большинства сущностей удаления в API нет вовсе.
"""


class _Confirm(BaseModel):
    confirm: bool = Field(description="Выполнить операцию в Tehzor?")


@dataclass
class State:
    settings: Settings
    client: TehzorClient | None = None
    pending: PendingStore = field(init=False)
    audit: AuditLog = field(init=False)
    cache: dict[str, tuple[float, str]] = field(default_factory=dict)
    sessions: int = 0
    owns_client: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    tree: ObjectTree | None = None
    tree_at: float = 0.0
    tree_diff: tuple[list[str], list[str]] = ([], [])
    tree_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    projects: ProjectsIndex = field(init=False)

    def __post_init__(self) -> None:
        self.pending = PendingStore(self.settings.confirm_ttl)
        self.audit = AuditLog(self.settings.audit_log)
        self.projects = ProjectsIndex(self.settings.projects)

    def require_client(self) -> TehzorClient:
        if self.client is None:
            raise ToolError("клиент Tehzor не инициализирован")
        return self.client


# --- сериализация и ошибки -------------------------------------------------------------------------


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True, context={"timestamps": "iso"})
    if isinstance(value, PreparedRequest):
        return {"method": value.method, "path": value.path, "query": dict(value.params) or None, "body": value.json}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return value


def dumps(value: Any) -> str:
    return json.dumps(to_jsonable(value), ensure_ascii=False, separators=(",", ":"), default=str)


_HTTP_MESSAGES = {
    errors.BadRequestError: "Неверный запрос (400)",
    errors.UnauthorizedError: "Нет авторизации (401): проверьте api-key",
    errors.ForbiddenError: "Нет доступа (403)",
    errors.NotFoundError: "Не найдено (404)",
    errors.ConflictError: "Конфликт (409)",
    errors.RateLimitError: "Превышен лимит запросов (429), повторите позже",
}


def tool_error(exc: Exception) -> ToolError:
    if isinstance(exc, ToolError):
        return exc
    if isinstance(exc, ValidationError):
        details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:10])
        return ToolError(f"Неверные параметры: {details}")
    if isinstance(exc, errors.QueryTooHeavyError):
        return ToolError(f"Запрос слишком тяжёлый для сервера: {exc.message}")
    if isinstance(exc, errors.TehzorHTTPError):
        title = next((m for cls, m in _HTTP_MESSAGES.items() if isinstance(exc, cls)), f"Ошибка API ({exc.status})")
        body = (exc.body or "")[:1000]
        return ToolError(
            f"{title}: {exc.message}" + (f"\nОтвет сервера: {body}" if body and body != exc.message else "")
        )
    if isinstance(exc, errors.ServiceUnavailableError):
        return ToolError(f"API временно недоступен (защита от перегрузки), повторите через {exc.retry_after:.0f} с")
    if isinstance(exc, errors.TehzorTimeoutError):
        return ToolError(f"Нет ответа от API: {exc}")
    if isinstance(exc, errors.ReadOnlyError):
        return ToolError(f"Запись запрещена: {exc}")
    if isinstance(exc, errors.TehzorError):
        return ToolError(str(exc))
    return ToolError(f"Внутренняя ошибка: {type(exc).__name__}: {exc}")


# --- обязательные фильтры для списков --------------------------------------------------------------


def _get(obj: Any, name: str) -> Any:
    return getattr(obj, name, None) if obj is not None else None


REQUIRED_FILTERS: dict[str, tuple[Callable[[dict[str, Any]], bool], str]] = {
    "problems_list": (
        lambda a: bool(_get(a.get("filters"), "objects") or _get(a.get("filters"), "spaces")),
        "укажите filters.objects (id объектов)",
    ),
    "spaces_list": (
        lambda a: bool(_get(a.get("filters"), "objects") or _get(a.get("filters"), "spaces")),
        "укажите filters.objects или filters.spaces",
    ),
    "tasks_list": (lambda a: bool(_get(a.get("filters"), "objects")), "укажите filters.objects"),
    "work_acceptances_list": (
        lambda a: bool(a.get("object_id") or _get(a.get("filters"), "work_acceptance_ids")),
        "укажите object_id",
    ),
    "internal_acceptances_list": (lambda a: bool(a.get("object_id")), "укажите object_id"),
    "comments_list": (
        lambda a: bool(_get(a.get("filters"), "problem_id") or _get(a.get("filters"), "work_acceptance_id")),
        "укажите filters.problem_id или filters.work_acceptance_id",
    ),
}


# --- генерация инструментов -------------------------------------------------------------------------


def _method(op: Operation) -> Callable[..., Any]:
    """Несвязанный метод класса ресурса — источник сигнатуры инструмента."""
    for cls in _resource_classes():
        if cls.resource_name == op.resource:
            return getattr(cls, op.name)  # type: ignore[no-any-return]
    raise KeyError(op.resource)


def _resource_classes() -> list[Any]:
    from ..resources._base import BaseResource

    found: list[Any] = []
    stack = list(BaseResource.__subclasses__())
    while stack:
        cls = stack.pop()
        found.append(cls)
        stack.extend(cls.__subclasses__())
    return found


def _description(op: Operation) -> str:
    parts = [op.summary or op.operation_id]
    if op.paginated:
        parts.append("Страница списка: limit (по умолчанию 50, максимум 500) и offset; в ответе next_offset.")
    if op.tool_name in REQUIRED_FILTERS:
        parts.append(f"Обязательно: {REQUIRED_FILTERS[op.tool_name][1]}.")
    if op.kind != "R":
        parts.append(
            "ИЗМЕНЯЕТ ДАННЫЕ в Tehzor. Не выполняется сразу: возвращает превью и confirmation_id; "
            "выполнить можно только после явного согласия пользователя (confirm_operation)."
        )
        if op.kind == "D":
            parts.append("Удаление необратимо.")
    if not op.documented:
        parts.append("(Метод не описан в официальной документации API.)")
    return " ".join(parts)


def _signature(method: Callable[..., Any]) -> tuple[list[inspect.Parameter], dict[str, Any]]:
    hints = typing.get_type_hints(method)
    params: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}
    for name, p in inspect.signature(method).parameters.items():
        if name in ("self", "dry_run"):
            continue
        ann = hints.get(name, Any)
        params.append(p.replace(kind=inspect.Parameter.KEYWORD_ONLY, annotation=ann))
        annotations[name] = ann
    return params, annotations


def build_tool(state: State, op: Operation) -> Callable[..., Awaitable[str]]:
    method = _method(op)
    params, annotations = _signature(method)
    params.append(inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context))
    annotations["ctx"] = Context
    annotations["return"] = str

    async def tool(**kwargs: Any) -> str:
        ctx: Context = kwargs.pop("ctx")  # type: ignore[type-arg]
        client = state.require_client()
        bound = getattr(getattr(client, op.resource), op.name)
        try:
            if op.kind == "R":
                return await _read(state, op, bound, kwargs)
            return await _write(state, op, bound, kwargs, ctx)
        except Exception as exc:
            raise tool_error(exc) from exc

    tool.__name__ = op.tool_name
    tool.__doc__ = _description(op)
    tool.__signature__ = inspect.Signature(params, return_annotation=str)  # type: ignore[attr-defined]
    tool.__annotations__ = annotations
    return tool


async def _read(state: State, op: Operation, bound: Callable[..., Any], kwargs: dict[str, Any]) -> str:
    check = REQUIRED_FILTERS.get(op.tool_name)
    if check and not check[0](kwargs):
        raise ToolError(f"{op.tool_name}: {check[1]} — без фильтра по объекту запрос слишком тяжёлый для сервера")
    if op.paginated:
        limit = int(kwargs.get("limit") or state.settings.default_limit)
        if limit < 1 or limit > state.settings.max_limit:
            raise ToolError(f"limit должен быть от 1 до {state.settings.max_limit}")
        offset = int(kwargs.get("offset") or 0)
        kwargs["limit"], kwargs["offset"] = limit, offset
        items = await bound(**kwargs)
        return dumps(
            {
                "items": items,
                "count": len(items),
                "offset": offset,
                "next_offset": offset + len(items) if len(items) == limit else None,
            }
        )
    return dumps(await bound(**kwargs))


async def _write(state: State, op: Operation, bound: Callable[..., Any], kwargs: dict[str, Any], ctx: Context) -> str:  # type: ignore[type-arg]
    s = state.settings
    if not s.allow_write:
        raise ToolError(
            f"{op.tool_name}: запись отключена администратором (TEHZOR_MCP_ALLOW_WRITE не задан). Запрос не отправлен."
        )
    if s.write_tools and op.tool_name not in s.write_tools:
        raise ToolError(
            f"{op.tool_name}: запись этим инструментом не разрешена (TEHZOR_MCP_WRITE_TOOLS). Запрос не отправлен."
        )
    request: PreparedRequest = await bound(**kwargs, dry_run=True)
    pending = state.pending.add(op, request)
    preview = {
        "tool": op.tool_name,
        "summary": op.summary,
        "request": to_jsonable(request),
        "irreversible": op.kind == "D",
    }
    state.audit.write(
        "preview",
        confirmation_id=pending.confirmation_id,
        tool=op.tool_name,
        request=request.describe(),
        body=request.json,
    )

    if _supports_elicitation(ctx):
        message = (
            f"Tehzor: {op.summary}\n{request.describe()}\n"
            f"Тело: {json.dumps(request.json, ensure_ascii=False)[:1500] if request.json is not None else '—'}"
            + ("\nВНИМАНИЕ: удаление необратимо." if op.kind == "D" else "")
        )
        try:
            answer = await ctx.elicit(message=message, schema=_Confirm)
        except Exception as exc:
            state.audit.write("elicitation_failed", confirmation_id=pending.confirmation_id, error=str(exc))
        else:
            if answer.action == "accept" and getattr(answer, "data", None) is not None and answer.data.confirm:
                taken = state.pending.pop(pending.confirmation_id)
                if taken is None:
                    raise ToolError("подтверждение истекло, повторите операцию")
                state.audit.write("confirmed", confirmation_id=pending.confirmation_id, via="elicitation")
                return await _execute(state, taken.op, taken.request, pending.confirmation_id)
            state.pending.discard(pending.confirmation_id)
            state.audit.write("declined", confirmation_id=pending.confirmation_id, action=answer.action)
            return dumps({"status": "declined", "message": "Пользователь отклонил операцию, запрос не отправлен"})

    return dumps(
        {
            "status": "pending_confirmation",
            "confirmation_id": pending.confirmation_id,
            "expires_in_seconds": int(s.confirm_ttl),
            "preview": preview,
            "instructions": "Покажите превью пользователю. Вызовите confirm_operation с этим confirmation_id "
            "только после его явного согласия. Без подтверждения запрос не будет отправлен.",
        }
    )


def _supports_elicitation(ctx: Context) -> bool:  # type: ignore[type-arg]
    try:
        caps = ctx.session.client_params.capabilities
        return caps.elicitation is not None
    except Exception:
        return False


async def _execute(state: State, op: Operation, request: PreparedRequest, confirmation_id: str) -> str:
    client = state.require_client()
    if client.transport.read_only:
        raise ToolError("клиент в режиме только чтения — запрос не отправлен")
    try:
        result = await client.transport.send(request, can_retry=op.idempotent)
    except Exception as exc:
        state.audit.write(
            "error", confirmation_id=confirmation_id, tool=op.tool_name, error=f"{type(exc).__name__}: {exc}"
        )
        raise
    state.audit.write("executed", confirmation_id=confirmation_id, tool=op.tool_name, request=request.describe())
    return dumps({"status": "done", "tool": op.tool_name, "result": result})


# --- сервер -------------------------------------------------------------------------------------------

DICTIONARIES: dict[str, tuple[str, str, str]] = {
    "tehzor://stages": ("objects", "stages", "Стадии объекта"),
    "tehzor://processes": ("objects", "processes", "Бизнес-процессы"),
    "tehzor://problem-statuses": ("problems", "statuses", "Статусы нарушений"),
    "tehzor://task-statuses": ("tasks", "statuses", "Статусы задач"),
    "tehzor://task-types": ("tasks", "types", "Типы задач"),
    "tehzor://work-acceptance-statuses": ("work_acceptances", "statuses", "Статусы приёмок работ"),
    "tehzor://work-acceptance-types": ("work_acceptances", "types", "Типы приёмок работ"),
    "tehzor://work-acceptance-front-types": ("work_acceptances", "front_types", "Типы фронта приёмок работ"),
    "tehzor://owner-acceptance-statuses": ("owner_acceptances", "statuses", "Статусы передач собственникам"),
    "tehzor://owner-acceptance-resolutions": ("owner_acceptances", "resolutions", "Решения собственников"),
    "tehzor://warranty-claim-statuses": ("warranty_claims", "statuses", "Статусы гарантийных заявлений"),
    "tehzor://check-list-statuses": ("check_lists", "statuses", "Статусы чек-листов"),
    "tehzor://check-item-statuses": ("check_lists", "item_statuses", "Статусы категорий чек-листов"),
    "tehzor://space-types": ("spaces", "types", "Типы помещений"),
    "tehzor://space-status-sets": ("spaces", "status_sets", "Наборы статусов помещений"),
    "tehzor://meter-types": ("spaces", "meter_types", "Типы приборов учёта"),
    "tehzor://contract-forms": ("spaces", "contract_forms", "Формы договоров"),
    "tehzor://decoration-sets": ("spaces", "decoration_sets", "Наборы типов отделки"),
}


def _make_client(s: Settings) -> TehzorClient:
    return TehzorClient(
        api_key=s.api_key,
        user_id=s.user_id,
        base_url=s.base_url,
        proxy=s.proxy,
        ssl=s.ssl_verify,
        max_concurrency=s.max_concurrency,
        rate_limit=s.rate_limit,
        read_only=not s.allow_write,
    )


def create_server(
    settings: Settings | None = None, *, client: TehzorClient | None = None, **fastmcp_kwargs: Any
) -> FastMCP:
    """Создать MCP-сервер. `client` — для тестов (иначе создаётся в lifespan по настройкам)."""
    s = settings or Settings.from_env()
    state = State(s, client)

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[State]:
        # lifespan вызывается на каждую сессию (в HTTP их несколько): один клиент на процесс, счётчик ссылок
        async with state.lock:
            if state.client is None:
                state.client = _make_client(s)
                state.owns_client = True
            state.sessions += 1
        try:
            yield state
        finally:
            async with state.lock:
                state.sessions -= 1
                if state.sessions == 0 and state.owns_client and state.client is not None:
                    await state.client.close()
                    state.client = None
                    state.owns_client = False

    mcp = FastMCP("tehzor", instructions=INSTRUCTIONS, lifespan=lifespan, **fastmcp_kwargs)
    mcp._tehzor_state = state  # type: ignore[attr-defined]

    for op in REGISTRY.all():
        if not op.mcp or (op.mutating and s.hide_write_tools):
            continue
        mcp.add_tool(
            build_tool(state, op),
            name=op.tool_name,
            description=_description(op),
            annotations=ToolAnnotations(
                title=op.summary or op.tool_name,
                readOnlyHint=op.kind == "R",
                destructiveHint=op.kind != "R",
                idempotentHint=op.idempotent,
                openWorldHint=True,
            ),
            structured_output=False,
        )

    if not s.hide_write_tools:

        @mcp.tool(
            name="confirm_operation",
            description="Выполнить ранее подготовленную изменяющую операцию по confirmation_id. "
            "Вызывать ТОЛЬКО после явного согласия пользователя с показанным превью.",
            annotations=ToolAnnotations(
                title="Подтвердить операцию",
                readOnlyHint=False,
                destructiveHint=True,
                idempotentHint=False,
                openWorldHint=True,
            ),
            structured_output=False,
        )
        async def confirm_operation(confirmation_id: str) -> str:
            if not s.allow_write:
                raise ToolError("запись отключена администратором (TEHZOR_MCP_ALLOW_WRITE не задан)")
            pending = state.pending.pop(confirmation_id)
            if pending is None:
                state.audit.write("confirm_rejected", confirmation_id=confirmation_id, reason="нет или истёк")
                raise ToolError("confirmation_id не найден или истёк — подготовьте операцию заново")
            state.audit.write("confirmed", confirmation_id=confirmation_id, via="confirm_operation")
            try:
                return await _execute(state, pending.op, pending.request, confirmation_id)
            except Exception as exc:
                raise tool_error(exc) from exc

    @mcp.tool(
        name="space_overview",
        description="Сводка по помещению: карточка, статус, приборы учёта, передачи собственникам, "
        "гарантийные обращения — одним вызовом.",
        annotations=ToolAnnotations(title="Сводка по помещению", readOnlyHint=True, openWorldHint=True),
        structured_output=False,
    )
    async def space_overview(space_id: str) -> str:
        c = state.require_client()
        try:
            space, status, meters, oas, claims = await asyncio.gather(
                c.spaces.get(space_id),
                c.spaces.get_status(space_id),
                c.spaces.meters(space_id),
                c.spaces.owner_acceptances(space_id),
                c.spaces.warranty_claims(space_id),
            )
        except Exception as exc:
            raise tool_error(exc) from exc
        return dumps(
            {"space": space, "status": status, "meters": meters, "owner_acceptances": oas, "warranty_claims": claims}
        )

    for uri, (resource, method, title) in DICTIONARIES.items():
        _add_dictionary(mcp, state, uri, resource, method, title)

    register_insights(mcp, state, dumps, tool_error)

    return mcp


def _add_dictionary(mcp: FastMCP, state: State, uri: str, resource: str, method: str, title: str) -> None:
    async def read() -> str:
        cached = state.cache.get(uri)
        if cached and time.monotonic() - cached[0] < state.settings.cache_ttl:
            return cached[1]
        data = dumps(await getattr(getattr(state.require_client(), resource), method)())
        state.cache[uri] = (time.monotonic(), data)
        return data

    mcp.resource(uri, name=uri.removeprefix("tehzor://"), title=title, description=title, mime_type="application/json")(
        read
    )
