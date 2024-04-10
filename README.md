# tehzor_api
## Методы API системы Техзор

В примере ниже обновления параметров квартир (площадь, плащадь БТИ, тип отделки) POST запросами API в асинхронном режиме.
Предварительно необходимо знать id квартир и id типа отделки.

```
async def main():     
    tehzor = await TehzorAPI.create(api_key=API_KEY, 
                                     user_id=USER_ID, 
                                     proxy=PROXIES.get("http")
                                     )
    async with asyncio.TaskGroup() as tg:
        for id, data in result_flats.items():
            tg.create_task(tehzor.update_spaces(id, data.model_dump_json()))
    await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
```


