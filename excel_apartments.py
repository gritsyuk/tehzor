import pandas as pd
import numpy as np
from tehzor.models_thz import Space

df = pd.read_excel( io = 'flat.xlsx')

flat_df = new_df = df[[ 
             "id_tehzor",
             "Площадь", 
             "ПИБ общ.", 
             "Отделка", 
            ]]

flats = flat_df.replace(np.nan, None).to_dict(orient='records')

result_flats = {}
for el in flats:
    id = el.get('id_tehzor')
    obj = Space(plannedArea=el.get('Площадь'), areaBTI=el.get('ПИБ общ.'), typeDecoration=el.get('Отделка'))
    result_flats[id] = obj
