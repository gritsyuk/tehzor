from pydantic import (BaseModel,
                      field_validator, 
                      EmailStr)
from typing import List
import re

class Space(BaseModel):
    plannedArea: float
    areaBTI: float
    typeDecoration: str | None

class Owner(BaseModel):
    name: str
    email: EmailStr = None
    additionalEmail: EmailStr = None
    phone: str = None
    additionalPhone: str = None
    comment: str = None
    spaces: List[str]
    
    @field_validator("email")
    def validate_email(cls, value):
        if not bool(re.fullmatch(r'[\w.-]+@[\w-]+\.[\w.]+', value)):
            raise ValueError("Email is invalid")
        return value 



    
    
# ------------------------------------------------- #
# params = {
#     "name": "Иванов Иван Иванович",
#     # "email": "example@example.ru",
#     # "additionalEmail": "example@example.ru",
#     # "phone": "333-222-333",
#     # "additionalPhone": "333-222-333",
#     # "comment": "какой-то комментарий",
#     "spaces": [
#         "string"
#     ]
# }


# owner = Owner(**params)
# print(owner.model_dump_json())