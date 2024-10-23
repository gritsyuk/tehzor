import asyncio
from tehzor import TehzorAPI, CONSTRUCT_STAGES
from tehzor.models import *
from config import API_KEY, USER_ID
from pprint import pprint


async def main():     
    try:
        data = []
        thz = await TehzorAPI.create(api_key=API_KEY,
                                     user_id=USER_ID
                                    )

        filters = ProblemFilter(
            objects=
            [
                "665caec29a2d1bef213ca6a0",

            ]
        )
        async for problem in thz.get_problems(limit=1000, filter=filters):
            valid_problem = Problem.model_validate(problem)
            stage_problem = CONSTRUCT_STAGES.get(valid_problem.stage).get("name")
            if stage_problem == "Гарантия":
                warranty = await thz.get_warranty_claims(valid_problem.links.warranty_claim_id)
                data.append(WarrantClaim.model_dump(warranty))
            pprint(data)
    except Exception as e:
        print(e)
    finally:
        await thz.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    