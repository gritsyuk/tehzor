from pydantic import (
    BaseModel,
    AliasGenerator,
    ConfigDict
)
from pydantic.alias_generators import to_camel, to_snake


class BaseTehzorModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
            serialization_alias=to_camel
        )
    )
