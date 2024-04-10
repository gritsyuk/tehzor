import asyncio
import pandas as pd
import tehzor.tehzor_models as tehzorModel
from tehzor.api import TehzorAPI
from config import API_KEY, USER_ID

async def main():     
    tehzor = await TehzorAPI.create(api_key=API_KEY, 
                                    user_id=USER_ID
                                    )
    data = []
    filters = tehzorModel.ProblemFilter(
        objects=["64480db0944e713c0cd68d6d"]
        )

    async for problem in tehzor.get_problems(filter=filters):
        valid_problem = tehzorModel.Problem.model_validate(problem)       
        fields = (
              valid_problem.id, 
              valid_problem.object.name, 
              valid_problem.stage, 
              valid_problem.number,
              valid_problem.status.name,
              valid_problem.category.name,
              valid_problem.createdAt,
              valid_problem.modifiedAt,
              valid_problem.createdBy.fullName,
              valid_problem.description
            )
        data.append(fields)



    
    df = pd.DataFrame(data)
    df.to_excel(excel_writer='problems.xlsx', index=False)
    
    await tehzor.session_close()

if __name__ == "__main__":    
    asyncio.run(main())
    