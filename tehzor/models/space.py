from pydantic import (
    BaseModel,
    Field,
    field_validator
)
from typing import List, Optional
from datetime import datetime
from .status import Status
from .user import User
from .base import BaseTehzorModel


class SpaceType(BaseTehzorModel):
    id: str
    name: str | None = None
    singular_name: str | None = None


class Space(BaseTehzorModel):

    id: str
    object_id: str
    name: str | None = None
    alt_name: str | None = None
    type: SpaceType
    status: Status
    indicators: List[str | None] = None
    floor: str | None = None
    planned_area: float | None = None
    actual_area: float | None = None
    type_decoration: str | None = None
    area_bti: float | None = Field(default=0., alias='areaBTI', alias_priority=100)
    number_bti: str | None = Field(default=None, alias='numberBTI', alias_priority=100)
    floor_bti: str | None = Field(default=None, alias='floorBTI', alias_priority=100)
    external_id: str | None = None
    contract_form: str | None = None
    markup_for_registration: bool = Field(default=True, exclude=True)
    created_by: User | None = None
    created_at: int | None = None
    modified_by: User | None = None
    decoration_warranty_expired_date: int | None = None
    constructive_warranty_expired_date: int | None = None
    technical_equipment_warranty_expired_date: int | None = None

    @field_validator('created_at', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value


class SpacesFilter(BaseModel):
    spaces: Optional[List[str]] = []