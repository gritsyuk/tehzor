from .base import BaseTehzorModel


class User(BaseTehzorModel):
    id: str | None = None
    full_name: str | None = None
    display_name: str | None = None
    position: str | None = None
    color: str | None = None
