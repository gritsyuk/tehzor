from pydantic import (
    BaseModel,
    field_validator,
)
from typing import List, Optional
from datetime import datetime
from .user import User


class SpaceMetersTariff(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class SpaceMeterType(BaseModel):
    id: str
    name: str
    measureUnit: str


class SpaceMetersConsumption(BaseModel):
    id: str | None = None
    value: str | None = None
    tariff: SpaceMetersTariff | None = None
    createdBy: User | None = None
    createdAt: int | None = None
    modifiedBy: User | None = None
    modifiedAt: int | None = None

    @field_validator('createdAt', 'modifiedAt', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value


class SpaceMeters(BaseModel):
    id: str
    type: SpaceMeterType | None
    serialNumber: str | None = None
    description: str | None = None
    consumptions: List[SpaceMetersConsumption] | None = None
    createdBy: User | None = None
    createdAt: int | None = None
    modifiedBy: User | None = None
    modifiedAt: int | None = None