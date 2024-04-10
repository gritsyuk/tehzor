import asyncio
from tehzor.api import TehzorAPI
from config import API_KEY, USER_ID
from excel_apartments import result_flats


async def main():     
    tehzor = await TehzorAPI.create(api_key=API_KEY, 
                                    user_id=USER_ID
                                    )
    async with asyncio.TaskGroup() as tg:
        for id, data in result_flats.items():
            tg.create_task(tehzor.update_spaces(id, data.model_dump_json()))

    await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    
    
