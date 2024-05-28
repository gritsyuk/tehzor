import asyncio
from tehzor.api import TehzorAPI
from config import API_KEY, USER_ID
from pprint import pprint


async def main():     
    thz = await TehzorAPI.create(api_key=API_KEY, user_id=USER_ID)

    async for res in thz.get_work_acceptances(object_id="65fad64beb908e0264317b76", limit=5000, offset=0):
        pprint(res)

    await thz.session_close()
if __name__ == "__main__":    
    asyncio.run(main())
    