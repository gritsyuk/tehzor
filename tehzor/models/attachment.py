from pydantic import (
    BaseModel
)
from typing import Optional


class Attachment(BaseModel):
    id: str
    preview: Optional[dict] = None
    full: Optional[dict] = None
    size: Optional[int] = None

