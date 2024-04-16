import pytest
from tehzor.api import TehzorAPI, TehzorAPIError
from tehzor.models_thz import WorkAcceptances
from config import API_KEY, USER_ID


@pytest.mark.asyncio
async def test_get_work_acceptance_success():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        res = await thz.get_work_acceptance("661a261d5d3aea11af15b08f")
        assert isinstance(res, WorkAcceptances)
    finally:
        await thz.session_close()


@pytest.mark.asyncio
async def test_get_work_acceptance_nonexistent_id():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        with pytest.raises(TehzorAPIError) as e:
            await thz.get_work_acceptance("nonexistent_id")
        assert "Request not found" in str(e.value)
    finally:
        await thz.session_close()
