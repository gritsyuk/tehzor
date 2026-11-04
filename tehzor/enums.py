"""Перечисления для тел запросов (значения из openapi.json, сверены со справочниками живого API).

В моделях ответов эти поля объявлены как `str`: появление нового значения на сервере не должно
ломать разбор. В запросах используются перечисления — неверное значение отсекается до отправки.
"""

from __future__ import annotations

from enum import Enum


class Stage(str, Enum):
    BUILDING = "building"
    ACCEPTANCE = "acceptance"
    TRANSFER = "transfer"
    WARRANTY = "warranty"


class ProcessId(str, Enum):
    OPERATIONAL_CONTROL = "operational-control"
    ACCEPTANCE_CONTROL = "acceptance-control"
    INCOMING_MATERIALS_CONTROL = "incoming-materials-control"
    INCOMING_DOCUMENTATION_CONTROL = "incoming-documentation-control"
    GEODETIC_CONTROL = "geodetic-control"
    LABORATORY_CONTROL = "laboratory-control"
    LABOR_PROTECTION_CONTROL = "labor-protection-control"
    INTERNAL_ACCEPTANCE = "internal-acceptance"
    PRESALE_CONTROL = "presale-control"
    UNITS_HANDOVER = "units-handover"
    OBJECT_HANDOVER = "object-handover"
    WARRANTY_SERVICE = "warranty-service"
    TECHNICAL_SERVICE = "technical-service"
    AUDIT = "audit"


class ProblemStatus(str, Enum):
    EXPIRED = "expired"
    WAITING = "waiting"
    HANDLING = "handling"
    VERIFICATION = "verification"
    FIXED = "fixed"
    CLOSED = "closed"


class TaskStatus(str, Enum):
    OPENED = "opened"
    ASSIGNED = "assigned"
    WORK_IN_PROGRESS = "work-in-progress"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


class TaskPriority(str, Enum):
    HIGHEST = "highest"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    LOWEST = "lowest"


class TaskType(str, Enum):
    AUDIT = "audit"
    CHECK = "check"
    ACCEPTANCE_CONTROL = "acceptance-control"
    TASK = "task"
    CHECKLIST_CALL = "checklist-call"
    SPACE_CALL = "space-call"
    WORK_ACCEPTANCE_CALL = "work-acceptance-call"


class LocationType(str, Enum):
    PLAN = "plan"
    SPACE = "space"


class WorkAcceptanceStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in-progress"
    PROBLEMS_IDENTIFIED = "problems-identified"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class WorkAcceptanceType(str, Enum):
    VISIBLE = "visible"
    HIDDENS = "hiddens"
    STRUCTURES_SAFETY = "structures-safety"


class FrontType(str, Enum):
    SPACES = "spaces"
    STRUCTURES = "structures"


class OwnerAcceptanceStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in-progress"
    DONE = "done"


class OwnerAcceptanceResolution(str, Enum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_PROBLEMS = "accepted-with-problems"
    REJECTED = "rejected"
    UNDEFINED = "undefined"


class CheckRecordStatus(str, Enum):
    NOT_CHECKED = "not-checked"
    WAITING = "waiting"
    WORK_IN_PROGRESS = "work-in-progress"
    PARTIALLY_ACCEPTED = "partially-accepted"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


class CommentType(str, Enum):
    PROBLEM_COMMENT = "problem-comment"
    WORK_ACCEPTANCE_COMMENT = "work-acceptance-comment"


class ProblemField(str, Enum):
    """Значения параметра `fields` у /warranty-claims/{id}/problems."""

    ID = "id"
    NUMBER = "number"
    STATUS = "status"
    DESCRIPTION = "description"
    PLANNED_FIX_DATE = "plannedFixDate"
    CATEGORY_ID = "categoryId"


class OwnerAcceptanceField(str, Enum):
    ID = "id"
    NUMBER = "number"
    RESOLUTION = "resolution"
    STATUS = "status"
    SPACE_OWNER_ID = "spaceOwnerId"
    ATTACHMENTS = "attachments"
    CREATED_AT = "createdAt"
    MODIFIED_AT = "modifiedAt"


class WarrantyClaimField(str, Enum):
    ID = "id"
    NUMBER = "number"
    STATUS = "status"
    ATTACHMENTS = "attachments"
    CREATED_AT = "createdAt"
    MODIFIED_AT = "modifiedAt"


class DecorationSetField(str, Enum):
    ID = "id"
    NAME = "name"
    SPACE_TYPES_DECORATIONS = "spaceTypesDecorations"
