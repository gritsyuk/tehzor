import asyncio
from tehzor.api import TehzorAPI
from config import API_KEY, USER_ID
from pprint import pprint


async def main():     
    try:
        thz = await TehzorAPI.create(api_key=API_KEY, 
                                     user_id=USER_ID
                                    )

        res = await thz.get_space("645fcdb772d3d1edf040b096")
        pprint(res)
    except Exception as e:
        print(e)
    finally:
        await thz.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    