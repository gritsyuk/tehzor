import pytest
from tehzor.api import TehzorAPI, TehzorAPIError
from tehzor.models import Space
from config import API_KEY, USER_ID


@pytest.mark.asyncio
async def test_get_space_success():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        res = await thz.get_space("645ce970b24de30d7c0a8afc")
        assert isinstance(res, Space)
    finally:
        await thz.session_close()


@pytest.mark.asyncio
async def test_get_space_nonexistent_id():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        with pytest.raises(TehzorAPIError) as e:
            await thz.get_space("nonexistent_id")
        assert "Request not found" in str(e.value)
    finally:
        await thz.session_close()
