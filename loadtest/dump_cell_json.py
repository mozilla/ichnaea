import json
from sqlalchemy import create_engine

engine = create_engine('mysql+pymysql://root:mysql@localhost/location')
connection = engine.connect()
result = connection.execute("select * from cell_measure")

RADIO_TYPE = {
    '': -1,
    'gsm': 0,
    'cdma': 1,
    'umts': 2,
    'lte': 3,
}

keys = RADIO_TYPE.keys()
for k, v in RADIO_TYPE.items():
    RADIO_TYPE[v] = k
for k in keys:
    del RADIO_TYPE[k]

for row in result:
    cell_data = [{"radio": RADIO_TYPE[row['radio']],
                  "mcc": row['mcc'],
                  "mnc": row['mnc'],
                  "lac": row['lac'],
                  "cid": row['cid']}]

    items = {"items": [{"lat": row['lat'],
             "lon": row['lon'],
             "accuracy": row['accuracy'],
             "altitude": row['altitude'],
             "altitude_accuracy": row['altitude_accuracy'],
             "radio": RADIO_TYPE[row['radio']],
             "cell": cell_data}]}
    jdata = json.dumps(items)
    print jdata
