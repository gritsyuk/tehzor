import re
from datetime import datetime
from pydantic import (
                      BaseModel,
                      field_validator,
                      EmailStr
                      )
from typing import List, Optional


class Space(BaseModel):
    plannedArea: float
    areaBTI: float
    typeDecoration: Optional[str | None] = None


class Owner(BaseModel):
    name: str
    email: EmailStr | None
    additionalEmail: Optional[EmailStr | None]
    phone: Optional[str | None]
    additionalPhone: Optional[str | None]
    comment: Optional[str | None]
    spaces: List[str]

    @field_validator("email")
    def validate_email(cls, value):
        if value:
            if not bool(re.fullmatch(r'[\w.-]+@[\w-]+\.[\w.]+', value)):
                raise ValueError("Email is invalid")
            return value
        else:
            return None


class Attachment(BaseModel):
    id: str
    preview: Optional[dict] = None
    full: Optional[dict] = None
    size: Optional[int] = None


class User(BaseModel):
    id: str
    fullName: Optional[str]
    displayName: Optional[str] = None
    position: Optional[str] = None
    color: Optional[str] = None


class Status(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class Construction(Status):
    pass


class Category(Status):
    pass


class Problem(BaseModel):
    id: str
    object: Construction
    links: Optional[dict] = None
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
    createdBy: User
    modifiedAt: int
    modifiedBy: User

    @field_validator('createdAt', 'modifiedAt', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value


class ProblemFilter(BaseModel):
    objects: Optional[List[str]] = []  # id строительх объектов
    spaces: Optional[List[str]] = []  # id помещений


class WorkScope(BaseModel):
    value: Optional[str] = None
    unitId: Optional[str] = None
    unitName: Optional[str] = None


class WorkAcceptances(Problem):
    class Config:
        exclude = {'object'}
    objectId: str
    structureIds: List[str]
    spaceIds: List[str]
    acceptanceDate: int
    percent: Optional[float] = 0.0
    comment: Optional[str] = None
    physicalWorkScope: Optional[WorkScope] = None
    type: Optional[str]
    frontType: Optional[str]
