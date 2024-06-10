from pydantic import (
    BaseModel
)
from typing import Optional


class Construction(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

