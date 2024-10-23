import pytest
from tehzor.api import TehzorAPI, TehzorAPIError
from tehzor.models.health_check import HealthCheck
from config import API_KEY, USER_ID


@pytest.mark.asyncio
async def test_health_check_success():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        res = await thz.health_check()
        print(res)
        assert res.status == "ok"
        assert isinstance(res, HealthCheck)
    finally:
        await thz.session_close()

