import re
from datetime import datetime
from pydantic import (BaseModel,
                      field_validator, 
                      EmailStr)
from typing import List, Optional, Any


class Space(BaseModel):
    plannedArea: float
    areaBTI: float
    typeDecoration: str | None

class Owner(BaseModel):
    name: str
    email: EmailStr | None
    additionalEmail: EmailStr | None
    phone: str | None
    additionalPhone: str | None
    comment: str | None
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
    fullName: str
    displayName: str
    position: str
    color: str

class Status(BaseModel):
    id: str
    name: str

class Constraction(Status):
    pass

class Category(Status):
    pass

class Problem(BaseModel):
    id: str
    object: Constraction
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
    respUsers: Optional[List[User]] = None
    watchers: Optional[List[User]] = None
    activeGroup: Optional[str] = None
    activeGroupLeader: Optional[User] = None
    initialGroup: Optional[str] = None
    initialGroupLeader: Optional[User] = None
    critical: Optional[bool] = None
    createdAt: int
    createdBy: User
    modifiedAt: int
    modifiedBy: User
    duration: Optional[int] = None

    @field_validator('createdAt', 'modifiedAt', mode='after')
    def convert_timestamps_to_datetime(cls, value):
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value
    

class ProblemFilter(BaseModel):
    objects: Optional[List[str]] = []
    spaces: Optional[List[str]] = []

    # @field_validator('duration', mode='before')
    # def calculate_duration(cls, v, values):
    #     if 'createdAt' in values and 'modifiedAt' in values:
    #         return int((values['modifiedAt'] - values['createdAt']))
    #     return v
    

# class ProblemDb(BaseModel):
#     id: str
#     object:
#     name:
#     stage:
#     number:
#     status:
#     category: Category
#     createdAt: datetime