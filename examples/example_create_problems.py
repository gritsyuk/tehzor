import asyncio
import json
from tehzor import TehzorAPI
# from tehzor.models import NewProblem
# from tehzor.models import ProblemLinks
from config import API_KEY, USER_ID
from pprint import pprint


async def main():     
    tehzor = await TehzorAPI.create(api_key=API_KEY, 
                                    user_id=USER_ID
                                    )

    new_problem_dict = dict( 
            links=dict(
                spaceId="65b0a1fb00dca856092261c0",
                ownerAcceptanceId="66e040fed1cd16da58c7a50c"
            ),
            objectId="641f10491ba6ce0024682f15",
            stage="transfer",
            processId="units-handover",
            categoryId="657fcfd9f6fc0f67cfe71e1e",
            floor="24",
            description="Тестовое нарушение 2"
        )

    new_problem = await tehzor.create_problem(data=json.dumps(new_problem_dict))
    pprint(new_problem)
    await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    