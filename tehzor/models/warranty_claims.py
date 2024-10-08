from pydantic import (
    BaseModel,
    Field
)
from datetime import datetime


class WarrantClaim(BaseModel):
    id: str
    number: int
    status: str
    created_at: datetime = Field(alias='createdAt')
    modified_at: datetime = Field(alias='modifiedAt')
