import pytest
from tehzor.api import TehzorAPI, TehzorAPIError
from tehzor.models import Problem
from config import API_KEY, USER_ID


@pytest.mark.asyncio
async def test_get_problem_success():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        res = await thz.get_problem("66196a83e9701bb00072ca06")
        assert isinstance(res, Problem)
    finally:
        await thz.session_close()


@pytest.mark.asyncio
async def test_get_problem_nonexistent_id():
    thz = await TehzorAPI.create(api_key=API_KEY,
                                 user_id=USER_ID
                                 )
    try:
        with pytest.raises(TehzorAPIError) as e:
            await thz.get_problem("nonexistent_id")
        assert "Request not found" in str(e.value)
    finally:
        await thz.session_close()
