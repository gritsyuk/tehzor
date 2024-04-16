import pytest
from tehzor.api import TehzorAPI, TehzorAPIError
from config import USER_ID


@pytest.mark.asyncio
async def test_api_create_unauthorized():
    api_key = "no-no"
    thz = await TehzorAPI.create(api_key=api_key,
                                 user_id=USER_ID
                                 )
    try:
        with pytest.raises(TehzorAPIError) as e:
            await thz.get_problem("nonexistent_id")
        assert "Unauthorized" in str(e.value)
    finally:
        await thz.session_close()
