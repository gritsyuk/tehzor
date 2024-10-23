from pydantic import (
    field_validator,
)
from typing import List, Optional
from datetime import datetime
from .user import User
from .problem import Problem
from .base import BaseTehzorModel


class WorkScope(BaseTehzorModel):
    value: Optional[str] = None
    unit_id: Optional[str] = None
    unit_name: Optional[str] = None


class WorkAcceptances(Problem):
    object_id: str
    structure_ids: List[str]
    space_ids: List[str] = []
    acceptance_date: int
    percent: Optional[float] = 0.0
    comment: Optional[str] = None
    physical_work_scope: Optional[WorkScope] = None
    plan_physical_work_scope: Optional[dict] = None
    type: Optional[str] = None
    front_type: Optional[str]
    acceptors: Optional[List[User | str]] = None
    acceptors_active_group: Optional[str] = None
    acceptors_active_group_leader: Optional[User | str] = None
    acceptors_initial_group: Optional[str] = None
    acceptors_initial_group_leader: Optional[User] = None

    @field_validator('created_at', 'modified_at', 'acceptance_date', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value
