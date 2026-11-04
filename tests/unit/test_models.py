from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from tehzor.models import ConstructionObject, TehzorModel, TehzorRequest, iter_extras
from tehzor.types import Timestamp, to_millis


class Stamped(TehzorModel):
    id: str
    created_at: Timestamp | None = None


class Child(TehzorModel):
    id: str


class Parent(TehzorModel):
    id: str
    child: Child | None = None
    items: list[Child] | None = None


class Body(TehzorRequest):
    object_id: str
    area_bti: float | None = None
    note: str | None = None


def test_timestamp_parses_millis_to_utc() -> None:
    m = Stamped.model_validate({"id": "1", "createdAt": 1633073425824})
    assert m.created_at == datetime(2021, 10, 1, 7, 30, 25, 824000, tzinfo=timezone.utc)
    assert m.model_dump(by_alias=True)["createdAt"] == 1633073425824


def test_timestamp_accepts_datetime_and_digit_string() -> None:
    dt = datetime(2025, 6, 14, 19, tzinfo=timezone.utc)
    assert Stamped(id="1", created_at=dt).created_at == dt
    assert Stamped.model_validate({"id": "1", "createdAt": "1749927600000"}).created_at == dt


def test_to_millis_naive_is_utc() -> None:
    assert to_millis(datetime(2025, 6, 14, 19)) == 1749927600000


def test_unknown_fields_are_kept_and_found() -> None:
    p = Parent.model_validate(
        {"id": "1", "newField": 1, "child": {"id": "c", "color": "#fff"}, "items": [{"id": "i", "x": None}]}
    )
    assert dict(iter_extras(p)) == {"newField": 1, "child.color": "#fff", "items[].x": None}


def test_only_id_required() -> None:
    obj = ConstructionObject.model_validate({"id": "uuid", "customFields": None})
    assert obj.custom_fields is None
    with pytest.raises(ValidationError):
        ConstructionObject.model_validate({"name": "без id"})


def test_request_to_api_camel_case_without_none() -> None:
    assert Body(object_id="o", area_bti=55.1).to_api() == {"objectId": "o", "areaBti": 55.1}
    assert Body.model_validate({"objectId": "o"}).object_id == "o"


def test_request_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Body(object_id="o", typo_field=1)  # type: ignore[call-arg]


def test_timestamp_iso_context() -> None:
    m = Stamped.model_validate({"id": "1", "createdAt": 1749927600000})
    assert m.model_dump(mode="json", context={"timestamps": "iso"})["created_at"] == "2025-06-14T19:00:00+00:00"
    assert m.model_dump(mode="json")["created_at"] == 1749927600000
