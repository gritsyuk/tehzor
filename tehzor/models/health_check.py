from pydantic import BaseModel
from typing import Optional


class Info(BaseModel):
    status: str
    message: Optional[str] = None


class StatusHealth(BaseModel):
    mongodb: Optional[Info] = None
    redis: Optional[Info] = None


class HealthCheck(BaseModel):
    status: str
    info: StatusHealth
    error: Optional[StatusHealth] = None
    details: StatusHealth
