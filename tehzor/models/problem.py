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
from .base import BaseTehzorModel


class ProblemLinks(BaseTehzorModel):
    space_id: Optional[str] = None
    check_id: Optional[str] = None
    internal_acceptance_id: Optional[str] = None
    owner_acceptance_id: Optional[str] = None
    warranty_claim_id: Optional[str] = None
    check_list_id: Optional[str] = None
    check_item_id: Optional[str] = None
    check_record_id: Optional[str] = None
    task_id: Optional[str] = None
    template_id: Optional[str] = None
    structure_id: Optional[str] = None
    workAcceptance_id: Optional[str] = None


class Reason(BaseModel):
    value: Optional[str] = None


class ProblemTag(BaseModel):
    id: str
    name: str


class Problem(BaseTehzorModel):
    id: str
    object: Optional[Construction] = Field(default=None, exclude=True)
    links: Optional[ProblemLinks] = None
    stage: str
    number: int
    status: Status
    planned_fix_date: Optional[int] = None
    category_id: str | dict = None
    category: Optional[Category] = Category(id="-", name="Без категории")
    problem_tags: Optional[List[ProblemTag]] = None
    reason: Optional[Reason] = None
    plan: Optional[Status] = None
    floor: Optional[str] = None
    display_location: Optional[str] = None
    description: Optional[str] = None
    prescription: Optional[str] = None
    attachments: Optional[List[Attachment]] = None
    performers: Optional[List[User | str]] = Field(default=None, exclude=True)
    watchers: Optional[List[User | str]] = None
    performers_active_group: Optional[str] = Field(default=None, exclude=True)
    performers_active_group_leader: Optional[User | str] = Field(default=None, exclude=True)
    performers_initial_group: Optional[str] = Field(default=None, exclude=True)
    performers_initial_group_leader: Optional[User] = Field(default=None, exclude=True)
    inspectors: Optional[List[Status]] = None
    inspectors_active_group: Optional[str] = None
    critical: Optional[bool] = False
    created_at: int
    created_by: Optional[User] = None
    modified_at: int
    modified_by: Optional[User] = None

    @field_validator('created_at', 'modified_at', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value


class ProblemFilter(BaseModel):
    objects: Optional[List[str]] = []
    spaces: Optional[List[str]] = []
