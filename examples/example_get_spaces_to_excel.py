import asyncio
from tehzor import TehzorAPI
from config import API_KEY
import pandas as pd


construction_site = {
    "64480db0944e713c0cd68d6d": "Жилой дом 1 секция 1",
    "64480e02944e713c0cd6a26d": "Жилой дом 1 секция 2",
    "64480fac944e713c0cd6d465": "Жилой дом 2 секция 1",
    "644813db944e713c0cd6f926": "Жилой дом 2 секция 2"
}


async def main():
    try:
        tehzor = await TehzorAPI.create(api_key=API_KEY)
        spaces_list = [space async for space in tehzor.get_spaces()]
        data = [
            {
                'id': space['id'],
                'name': space['name'],
                'object_id': space['object_id'],
                'object_name': construction_site.get(space['object_id']),
                'type.name': space['type']['name'],
                'floor': space['floor']
            }
            for space in spaces_list if space['object_id'] in construction_site and space['type']['name'] == 'Квартиры'
        ]
        df = pd.DataFrame(data)
        df['name'] = pd.to_numeric(df['name'], errors='coerce').astype('Int64')
        df_sorted = df.sort_values(by=['object_id', 'name'])
        df_sorted.to_excel('spaces.xlsx', index=False)
    except Exception as e:
        print(e)
    finally:
        await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    