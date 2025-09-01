from .base import BaseTehzorModel
from  typing import Optional, List


class Location(BaseTehzorModel):
    sectors: Optional[List[str]] = None
    points: Optional[List[str]] = None
    map_points: Optional[List[str]] = None

