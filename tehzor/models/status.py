from pydantic import (
    BaseModel
)


class Status(BaseModel):
    id: str | None = None
    name: str | None = None

