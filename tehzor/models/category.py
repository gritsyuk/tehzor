from pydantic import (
    BaseModel
)
from typing import Optional


class Category(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

