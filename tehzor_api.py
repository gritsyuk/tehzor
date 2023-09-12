from aiohttp import ClientSession
from asyncio import Semaphore

class Tehzor_API(object):
    def __init__(self) -> None:
        pass
    
    @classmethod
    async def create(cls, 
                     api_key: str, 
                     url_api: str = "https://api.tehzor.ru", 
                     user_id: str = None, 
                     proxy: str = None,
                     limit_threads: int = 75):
        self = cls()
        self.url_api = url_api
        self.user_id = user_id 
        self.headers =  {
                        "Content-Type": "application/json",
                        "api-key": api_key
                        }
        self.proxy = proxy
        self.semaphore = Semaphore(limit_threads)  
        self.session = ClientSession(base_url=self.url_api, headers=self.headers)
        
        return self
    
    async def session_close(self):
        await self.session.close() 
           
    async def get_problems(self, limit: int = 1, offset: int = 0):
        url = r"/problems"
        params = dict(userId=self.user_id, limit=limit, offset=offset)
        async with self.session.get(url, params=params, proxy=self.proxy) as r:
            assert r.status == 200
            return await r.json()
    
    async def get_problem(self, id: str) -> dict:
        url = fr"/problems/{id}"
        async with self.session.get(url, proxy=self.proxy) as r:
            assert r.status == 200
            return await r.json()
            
    async def update_problem(self, id: str, data: dict):
        url = fr"/problems/{id}"
        async with self.session.post(url, data = data, proxy=self.proxy) as r:
            assert r.status == 201
            return await r.json()
            
    async def get_contract_forms(self) -> dict:
        url = r"/contract-forms"
        async with self.session.get(url, proxy=self.proxy) as r:
            assert r.status == 200
            return await r.json()
    
    async def create_owners(self, data: dict):
        url = fr"/space-owners"
        async with self.session.post(url, data = data, proxy=self.proxy) as r:
            assert r.status == 200
            return await r.json()
    
    async def update_spaces(self, id: str, data: dict):
        url = fr"/spaces/{id}"
        async with self.semaphore:
            async with self.session.post(url, data = data, proxy=self.proxy) as r:
                print(r.status,'   ',id, ' ----->  ', data)
                assert r.status == 201
                
    
    