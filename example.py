import asyncio
from tehzor.api import TehzorAPI
import tehzor.models_thz as tehzorModel
from config import API_KEY, USER_ID
from pprint import pprint


async def main():     
    tehzor = await TehzorAPI.create(api_key=API_KEY, 
                                    user_id=USER_ID
                                    )

    filters = tehzorModel.ProblemFilter(
        objects=["641ef54d1ba6ce0024681763"]
        )

    async for res in tehzor.get_problems(limit=2, filter=filters):
        pprint(res)

    await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    