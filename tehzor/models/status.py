from pydantic import (
    BaseModel
)
from typing import Optional


class Status(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

