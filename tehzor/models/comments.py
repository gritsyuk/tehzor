"""Комментарии и официальные ответы. Сверено с живым API 2026-11-04."""

from __future__ import annotations

from ..enums import CommentType
from ..types import Timestamp
from ._base import TehzorModel, TehzorRequest
from .common import AttachmentList, User


class CommentLinks(TehzorModel):
    problem_id: str | None = None
    check_id: str | None = None
    presale_check_id: str | None = None
    space_id: str | None = None
    owner_acceptance_id: str | None = None
    warranty_claim_id: str | None = None
    internal_acceptance_id: str | None = None
    work_acceptance_id: str | None = None
    structure_id: str | None = None


class Comment(TehzorModel):
    """Комментарий. fact: `number` бывает null; attachments — объекты; у пользователей есть `employers`."""

    id: str
    object_id: str | None = None
    comment_type_id: str | None = None
    links: CommentLinks | None = None
    ancestors: list[str] | None = None
    parent_id: str | None = None
    stage: str | None = None
    number: int | None = None
    description: str | None = None
    attachments: AttachmentList | None = None
    official: bool | None = None
    created_at: Timestamp | None = None
    created_by: User | None = None
    modified_at: Timestamp | None = None
    modified_by: User | None = None


class CommentFilters(TehzorRequest):
    """Тело `POST /comments/get-comments`."""

    problem_id: str | None = None
    work_acceptance_id: str | None = None
    comment_type_id: CommentType | None = None
    official: bool | None = None


class CommentLinksInput(TehzorRequest):
    problem_id: str | None = None
    check_id: str | None = None
    presale_check_id: str | None = None
    space_id: str | None = None
    owner_acceptance_id: str | None = None
    warranty_claim_id: str | None = None
    internal_acceptance_id: str | None = None
    work_acceptance_id: str | None = None
    structure_id: str | None = None


class CommentCreate(TehzorRequest):
    """Тело `POST /comments`. Проверяется только на заглушках."""

    comment_type_id: CommentType
    links: CommentLinksInput
    official: bool = False
    """True — официальный ответ, False — обычный комментарий."""
    parent_id: str | None = None
    description: str | None = None
    attachments: list[str] | None = None
    created_by: str | None = None
