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
               res.initialGroup,
               res.objectId,
               res.status.name,
               res.category.name,
               res.floor,
               res.description,
               res.createdAt,
               res.acceptanceDate,
               res.comment,
               res.percent,
               res.physicalWorkScope.value,
               res.physicalWorkScope.unitName,
               ",".join(str(element) for element in res.structureIds),
               ",".join(str(element) for element in res.spaceIds),
               res.frontType
               ]
        sheet.append(row)
    workbook.save("Приемки.xlsx")
    await thz.session_close()


if __name__ == "__main__":    
    asyncio.run(main())
    