# ![logo Tehzor](https://tehzor.com/images/components/Header/logo.svg)

## Обертка над  API системы Техзор на python (async/await)
Официальная документация [https://api.tehzor.ru/docs](https://api.tehzor.ru/docs)

## Установка

```bash
pip install tehzor
```

## Примеры
Обновления параметров квартир (площадь, плащадь БТИ, тип отделки). Предварительно необходимо знать id квартир и id типа отделки:
```python
from tehzor import TehzorAPI
from excel_apartments import result_flats


API_KEY = "00000000-0000-0000-0000-000000000000"
USER_ID = "123d7cdfc7ea123d123456ab"


async def main():     
    thz = await TehzorAPI.create(api_key=API_KEY, 
                                 user_id=USER_ID
                                )
    async with asyncio.TaskGroup() as tg:
        for id, data in result_flats.items():
            tg.create_task(thz.update_spaces(id, data.model_dump_json()))
    await thz.session_close()


if __name__ == "__main__":    
    asyncio.run(main())
```

