import asyncio
from tehzor import TehzorAPI
from tehzor.models import SpacesFilter
from config import API_KEY
import json


async def main():
    try:
        tehzor = await TehzorAPI.create(api_key=API_KEY)
        spaces_list = [space async for space in tehzor.get_spaces()]
        with open('spaces.json', 'w', encoding='utf-8') as f:
            json.dump(spaces_list, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(e)
    finally:
        await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    