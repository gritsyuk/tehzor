from typing import List
from .base import BaseTehzorModel


class DecorationType(BaseTehzorModel):
    id: str
    name: str
    space_types: List[str] | None = None


class DecorationList(BaseTehzorModel):
    id: str
    name: str
    space_types_decorations: List[DecorationType]
