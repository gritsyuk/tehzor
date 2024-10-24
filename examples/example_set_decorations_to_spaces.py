import pandas as pd
import asyncio
from tehzor import TehzorAPI
from tehzor.models import SpaceUpdate
from config import API_KEY


async def main():
    try:
        thz = await TehzorAPI.create(api_key=API_KEY)

        df = pd.read_excel("space_table.xlsx")
        df_filtered = df[["spaces_id", "decor_id"]].dropna(subset=["decor_id"])
        df_filtered = df_filtered[df_filtered['decor_id'] != '']

        async with asyncio.TaskGroup() as tg:
            for _, row in df_filtered.iterrows():
                tg.create_task(thz.update_spaces(
                    id=row['spaces_id'],
                    data=SpaceUpdate(
                        type_decoration=row['decor_id'],
                    ).model_dump_json(exclude_none=True, by_alias=True)
                )
                )
    except Exception as e:
        print(e)
    finally:
        await thz.session_close()


if __name__ == '__main__':
    asyncio.run(main())
