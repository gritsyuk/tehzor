import asyncio
from tehzor.api import TehzorAPI
from config import API_KEY, USER_ID
from openpyxl import Workbook
from pprint import pprint


async def main():     
    thz = await TehzorAPI.create(api_key=API_KEY, user_id=USER_ID)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Приемки работ"

    headers = [
        "Number", "Initial Group", "Object ID", "Status", "Category", "Floor",
        "Description", "Created At", "Acceptance Date", "Comment", "Percent",
        "Physical Work Scope Value", "Physical Work Scope Unit Name", "Structure IDs",
        "Space IDs", "Front Type"
    ]
    sheet.append(headers)

    async for res in thz.get_work_acceptances(object_id="65fad64beb908e0264317b76", limit=5000, offset=0):
        row = [res.number,
               res.acceptors_initial_group,
               res.object_id,
               res.status.name,
               res.category.name,
               res.floor,
               res.description,
               res.created_at,
               res.acceptance_date,
               res.comment,
               res.percent,
               res.physical_work_scope.value,
               res.physical_work_scope.unit_name,
               ",".join(str(element) for element in res.structure_ids),
               ",".join(str(element) for element in res.space_ids),
               res.front_type
               ]
        sheet.append(row)
    workbook.save("Приемки.xlsx")
    await thz.session_close()


if __name__ == "__main__":    
    asyncio.run(main())
    