from pydantic import (
    BaseModel
)
from typing import Optional


class User(BaseModel):
    id: Optional[str] = None
    fullName: Optional[str] = None
    displayName: Optional[str] = None
    position: Optional[str] = None
    color: Optional[str] = None
