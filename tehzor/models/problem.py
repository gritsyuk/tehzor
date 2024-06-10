from pydantic import (
    BaseModel,
    field_validator,
    Field
)
from datetime import datetime
from typing import List, Optional
from .attachment import Attachment
from .category import Category
from .construction import Construction
from .status import Status
from .user import User


class ProblemLinks(BaseModel):
    spaceId: Optional[str] = None
    checkId: Optional[str] = None
    internalAcceptanceId: Optional[str] = None
    ownerAcceptanceId: Optional[str] = None
    warrantyClaimId: Optional[str] = None
    checkListId: Optional[str] = None
    checkItemId: Optional[str] = None
    checkRecordId: Optional[str] = None
    taskId: Optional[str] = None
    templateId: Optional[str] = None
    structureId: Optional[str] = None
    workAcceptanceId: Optional[str] = None


class Problem(BaseModel):
    id: str
    object: Optional[Construction] = Field(default=None, exclude=True)
    links: Optional[ProblemLinks] = None
    stage: str
    number: int
    status: Status
    plannedFixDate: Optional[int] = None
    categoryId: str | dict = None
    category: Optional[Category] = Category(id="-", name="Без категории")
    plan: Optional[dict] = None
    floor: Optional[str] = None
    displayLocation: Optional[str] = None
    description: Optional[str] = None
    prescription: Optional[str] = None
    attachments: Optional[List[Attachment]] = None
    respUsers: Optional[List[User | str]] = None
    watchers: Optional[List[User | str]] = None
    activeGroup: Optional[str] = None
    activeGroupLeader: Optional[User | str] = None
    initialGroup: Optional[str] = None
    initialGroupLeader: Optional[User] = None
    critical: Optional[bool] = None
    createdAt: int
    createdBy: Optional[User] = None
    modifiedAt: int
    modifiedBy: Optional[User] = None

    @field_validator('createdAt', 'modifiedAt', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value


class ProblemFilter(BaseModel):
    objects: Optional[List[str]] = []  # id строительх объектов
    spaces: Optional[List[str]] = []  # id помещений
