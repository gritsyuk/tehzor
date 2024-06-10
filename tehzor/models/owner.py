from pydantic import (
    BaseModel,
    EmailStr,
    field_validator,
)
from typing import Optional, List
import re


class Owner(BaseModel):
    name: str
    email: EmailStr | None
    additionalEmail: Optional[EmailStr | None]
    phone: Optional[str | None]
    additionalPhone: Optional[str | None]
    comment: Optional[str | None]
    spaces: List[str]

    @field_validator("email")
    def validate_email(cls, value):
        if value:
            if not bool(re.fullmatch(r'[\w.-]+@[\w-]+\.[\w.]+', value)):
                raise ValueError("Email is invalid")
            return value
        else:
            return None
