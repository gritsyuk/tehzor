from pydantic import (
    BaseModel,
    Field,
    field_validator,
)
from typing import List
from datetime import datetime
from .status import Status
from .user import User


class Spacetype(BaseModel):
    id: str
    name: str | None = None
    singularName: str | None = None

class Space(BaseModel):
    id: str
    objectId: str
    name: str | None = None
    altName: str | None = None
    type: Spacetype
    status: Status
    indicators: List[str | None] = None
    floor: str | None = None
    plannedArea: float | None = None
    actualArea: float | None = None
    typeDecoration: str | None = None
    areaBTI: float | None = None
    numberBTI: str | None = None
    floorBTI: str | None = None
    externalId: str | None = None
    contractForm: str | None = None
    markupForRegistration: bool = Field(default=True, exclude=True)
    createdBy: User | None = None
    createdAt: int
    modifiedBy: User | None = None
    decorationWarrantyExpiredDate: int | None = None
    constructiveWarrantyExpiredDate: int | None = None
    technicalEquipmentWarrantyExpiredDate: int | None = None

    @field_validator('createdAt', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value
