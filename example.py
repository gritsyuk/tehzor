import asyncio
from tehzor.api import TehzorAPI
import tehzor.tehzor_models as tehzorModel
from config import API_KEY, USER_ID
from pprint import pprint


async def main():     
    tehzor = await TehzorAPI.create(api_key=API_KEY, 
                                    user_id=USER_ID
                                    )

    filters = tehzorModel.ProblemFilter(
        objects=["64c0fdfe46c4793df12beead"]
        )

    async for res in tehzor.get_problems(limit=2, filter=filters):
        pprint(res)

    await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    