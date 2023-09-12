import asyncio
from tehzor_api import Tehzor_API
from config import API_KEY, PROXIES, USER_ID
from excel import result_flats


async def main():     
    tehzor = await Tehzor_API.create(api_key=API_KEY, 
                                     user_id=USER_ID, 
                                     proxy=PROXIES.get("http")
                                     )
    async with asyncio.TaskGroup() as tg:
        for id, data in result_flats.items():
            tg.create_task(tehzor.update_spaces(id, data.model_dump_json()))

    await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    
    
