import asyncio
import pandas as pd
from tehzor.models import Problem, ProblemFilter
from tehzor import TehzorAPI
from tehzor.constants import CONSTRUCT_STAGES
from config import API_KEY, USER_ID, CONSTRUCTION


async def main():     
    tehzor = await TehzorAPI.create(api_key=API_KEY, 
                                    user_id=USER_ID
                                    )
    data = []

    # construct_keys = ["beside1_1_1", "beside1_1_2", "beside1_2_1", "beside1_2_2"]
    construct_keys = ["mitino_k18_1", "mitino_k18_2", "mitino_k18_3", "mitino_k18_4"]
    filters = ProblemFilter(
        objects=[CONSTRUCTION[id] for id in construct_keys]
        )
    try:
        async for problem in tehzor.get_problems(limit=50000, filter=filters):
            valid_problem = Problem.model_validate(problem)
            url_problem = f'=HYPERLINK("https://app.tehzor.ru/objects/{valid_problem.object.id}/problems/{valid_problem.id}", "Открыть")'
            stage_problem = CONSTRUCT_STAGES.get(valid_problem.stage).get("name")       
            fields = (
                url_problem, 
                valid_problem.object.name, 
                stage_problem, 
                valid_problem.number,
                valid_problem.status.name,
                valid_problem.category.name,
                valid_problem.floor,
                valid_problem.displayLocation,
                valid_problem.createdAt,
                valid_problem.modifiedAt,
                valid_problem.createdBy.fullName,
                valid_problem.description
                )
            data.append(fields)
 
        df = pd.DataFrame(data)
        df.to_excel(excel_writer='problems_k18.xlsx', index=False)
    except Exception as e:
        print(f"Произошла ошибка: {e}")
    finally:
        await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    