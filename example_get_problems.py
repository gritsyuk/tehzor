import asyncio
from tehzor import TehzorAPI
from tehzor.models import ProblemFilter
from config import API_KEY, USER_ID
from pprint import pprint


async def main():     
    tehzor = await TehzorAPI.create(api_key=API_KEY, 
                                    user_id=USER_ID
                                    )

    filters = ProblemFilter(
        objects=["641f0fe41ba6ce0024682d44"]
        )

    async for res in tehzor.get_problems(limit=2, filter=filters):
        pprint(res)

    await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    