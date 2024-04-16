from aiohttp import ClientSession, ClientResponse
from asyncio import Semaphore
from typing import List, AsyncGenerator, Optional
from .models import ProblemFilter, Problem, WorkAcceptances


class TehzorAPIError(Exception):
    pass


class TehzorAPI(object):
    def __init__(self) -> None:
        pass

    @classmethod
    async def create(cls,
                     api_key: str,
                     url_api: str = "https://api.tehzor.ru",
                     user_id: str = None,
                     proxy: str = None,
                     limit_threads: int = 25):
        self = cls()
        self.url_api = url_api
        self.user_id = user_id
        self.headers = {
            "Content-Type": "application/json",
            "api-key": api_key
        }
        self.proxy = proxy
        self.semaphore = Semaphore(limit_threads)
        self.session = ClientSession(base_url=self.url_api, headers=self.headers)

        return self

    async def session_close(self):
        await self.session.close()

    async def _handle_response(self, response: ClientResponse):
        try:
            if response.status == 200 or response.status == 201:
                return
            elif response.status == 400:
                raise TehzorAPIError(f"ERROR {response.status}: Error while fetching the violation list")
            elif response.status == 401:
                raise TehzorAPIError(f"ERROR {response.status}: Unauthorized (api-key not provided)")
            elif response.status == 403:
                raise TehzorAPIError(f"ERROR {response.status}: Access forbidden")
            elif response.status == 404:
                raise TehzorAPIError(f"ERROR {response.status}: Request not found")
            elif response.status == 500:
                raise TehzorAPIError(f"ERROR {response.status}: Server error")
            elif response.status == 502:
                raise TehzorAPIError(f"ERROR {response.status}: Server limit exceeded 0.5 Mb or other server error")
            else:
                raise TehzorAPIError(f"Unhandled status code: {response.status}")
        except TehzorAPIError:
            await self.session.close()
            raise

    async def get_problem(self, id: str) -> Problem:
        url = f"/problems/{id}"
        async with self.session.get(url,
                                    proxy=self.proxy,
                                    verify_ssl=False) as r:
            await self._handle_response(r)
            res_json = await r.json()

            return Problem.model_validate(res_json)

    async def get_problems(self,
                           user_id: str = None,  
                           limit: int = 50000,
                           offset: int = 0, 
                           filter: Optional[ProblemFilter] = None) -> AsyncGenerator[Problem, None]:
        url = r"/problems"
        if not user_id and self.user_id:
            user_id = self.user_id
        params = dict(userId=user_id,
                      limit=limit, 
                      offset=offset)
        filter_json = filter.model_dump() if filter else None
        async with self.session.get(url, 
                                    params=params, 
                                    proxy=self.proxy, 
                                    json=filter_json) as r:
            await self._handle_response(r)
            res_json = await r.json()
            for data in res_json:
                yield Problem.model_validate(data)
    
    async def get_work_acceptance(self, id: str) -> WorkAcceptances:
        url = f"/work-acceptances/{id}"
        async with self.session.get(url,
                                    proxy=self.proxy,
                                    verify_ssl=False) as r:
            await self._handle_response(r)
            res_json = await r.json()
            return WorkAcceptances.model_validate(res_json)

    async def get_work_acceptances(self,
                                   object_id: str= "",
                                   limit: int = 50000,
                                   offset: int = 0,
                                   ) -> AsyncGenerator[WorkAcceptances, None]:
        url = "/work-acceptances"
        params = dict(objectId=object_id,
                      limit=limit, 
                      offset=offset)
        async with self.session.get(url,
                                    params=params,
                                    proxy=self.proxy,
                                    verify_ssl=False) as r:
            await self._handle_response(r)
            res_json = await r.json()
            for data in res_json:
                yield WorkAcceptances.model_validate(data)

    async def update_problem(self, id: str, data: dict):
        url = fr"/problems/{id}"
        async with self.session.post(url,
                                     data=data,
                                     proxy=self.proxy,
                                     verify_ssl=False) as r:
            assert r.status == 201
            return await r.json()
    
    # async def create_problem(self, data: ProblemNew) -> Problem:
    #     url = fr"/problems"
    #     async with self.session.post(url,
    #                                  data=data,
    #                                  proxy=self.proxy,
    #                                  verify_ssl=False) as r:
            # assert r.status == 201
            # return await r.json()

    async def get_contract_forms(self) -> dict:
        url = r"/contract-forms"
        async with self.session.get(url,
                                    proxy=self.proxy,
                                    verify_ssl=False) as r:
            assert r.status == 200
            return await r.json()

    async def create_owners(self, data: dict):
        url = fr"/space-owners"
        async with self.semaphore:
            async with self.session.post(url,
                                         data=data,
                                         proxy=self.proxy,
                                         verify_ssl=False) as r:
                assert r.status == 201

    async def update_spaces(self, id: str, data: dict):
        url = fr"/spaces/{id}"
        async with self.semaphore:
            async with self.session.post(url,
                                         data=data,
                                         proxy=self.proxy,
                                         verify_ssl=False) as r:
                assert r.status == 201
