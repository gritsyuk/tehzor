from pydantic import (
    BaseModel,
    field_validator,
)
from typing import List
from datetime import datetime
from .user import User
from .base import BaseTehzorModel


class SpaceMetersTariff(BaseModel):
    id: str | None = None
    name: str | None = None


class SpaceMeterType(BaseTehzorModel):
    id: str
    name: str
    measure_unit: str


class SpaceMetersConsumption(BaseTehzorModel):
    id: str | None = None
    value: str | None = None
    tariff: SpaceMetersTariff | None = None
    created_by: User | None = None
    created_at: int | None = None
    modified_by: User | None = None
    modified_at: int | None = None

    @field_validator('created_at', 'modified_at', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value


class SpaceMeters(BaseTehzorModel):
    id: str
    type: SpaceMeterType | None
    serial_number: str | None = None
    description: str | None = None
    consumptions: List[SpaceMetersConsumption] | None = None
    created_by: User | None = None
    created_at: int | None = None
    modified_by: User | None = None
    modified_at: int | None = None