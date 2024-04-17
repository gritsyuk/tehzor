import pytest
from tehzor.api import TehzorAPI, TehzorAPIError
from tehzor.models import SpaceMeters
from typing import List
from config import API_KEY, USER_ID


@pytest.mark.asyncio
async def test_get_space_meters_success():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        res = await thz.get_space_meters("65b0a0fa00dca85609216435")
        assert isinstance(res[0], SpaceMeters)
    finally:
        await thz.session_close()



@pytest.mark.asyncio
async def test_get_space_meters_nonemeters():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        with pytest.raises(TehzorAPIError) as e:
            await thz.get_space_meters("65b0a0fa00dca85609216432")
        assert "404" in str(e.value)
    finally:
        await thz.session_close()


@pytest.mark.asyncio
async def test_get_space_meters_nonespace():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        with pytest.raises(TehzorAPIError) as e:
            await thz.get_space_meters("65b0a0fa00dca856092164aa")
        assert "400" in str(e.value)
    finally:
        await thz.session_close()