import asyncio
from tehzor import TehzorAPI
from tehzor.models import SpacesFilter
from config import API_KEY, USER_ID
from pprint import pprint
import json


async def main():
    try:
        tehzor = await TehzorAPI.create(api_key=API_KEY,
                                        user_id=USER_ID,
                                        verify_ssl=False
                                        )

        filters = SpacesFilter(
            spaces=["645fcdb772d3d1edf040b096"]
            )
        spaces_list = [space async for space in tehzor.get_spaces(filter=filters)]
        with open('spaces.json', 'w', encoding='utf-8') as f:
            json.dump(spaces_list, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(e)
    finally:
        await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    