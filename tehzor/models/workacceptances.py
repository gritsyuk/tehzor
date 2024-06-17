from pydantic import (
    BaseModel,
    field_validator,
    Field
)
from typing import List, Optional
from datetime import datetime
from .problem import Problem
from .user import User


class WorkScope(BaseModel):
    value: Optional[str] = None
    unitId: Optional[str] = None
    unitName: Optional[str] = None


class WorkAcceptances(Problem):
    objectId: str
    structureIds: List[str]
    spaceIds: List[str] = []
    acceptanceDate: int
    percent: Optional[float] = 0.0
    comment: Optional[str] = None
    physicalWorkScope: Optional[WorkScope] = None
    planPhysicalWorkScope: Optional[dict] = None
    type: Optional[str] = None
    frontType: Optional[str]
    acceptors: Optional[List[User | str]] = None
    acceptorsActiveGroup: Optional[str] = None
    acceptorsActiveGroupLeader: Optional[User | str] = None
    acceptorsInitialGroup: Optional[str] = None
    acceptorsInitialGroupLeader: Optional[User] = None

    @field_validator('createdAt', 'modifiedAt', 'acceptanceDate', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value
