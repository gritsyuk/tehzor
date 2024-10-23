from datetime import datetime
from .base import BaseTehzorModel


class WarrantClaim(BaseTehzorModel):
    id: str
    number: int
    status: str
    created_at: datetime
    modified_at: datetime
