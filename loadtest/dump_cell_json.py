import json
from collections import OrderedDict
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

# Build up a set of data based on the unique key per tower,
# then append a list of all lat/long pairs that were observed for that
# tower

all_towers = {}
key_to_dict = {}

for row in result:
    if row['psc'] != '-1':
        odict = OrderedDict()
        for k in [u'cid', u'lac', u'mcc', u'mnc', u'psc', u'radio']:
            v = row[k]
            odict[k] = v

        location = (row['lat'], row['lon'])

        key = tuple(odict.values())
        key_to_dict[key] = odict
        all_towers.setdefault(key, [])
        if len(all_towers[key]) < 10:
            all_towers[key].append(location)

#pprint(all_towers)


for key in all_towers:
    odict = key_to_dict[key]
    cell_data = [{"radio": RADIO_TYPE[odict['radio']],
                  "mcc": odict['mcc'],
                  "mnc": odict['mnc'],
                  "lac": odict['lac'],
                  "cid": odict['cid']}]
    items = {"items": []}
    for (lat, lon) in all_towers[key]:
        data = {"lat": lat,
                "lon": lon,
                "accuracy": 1,
                "altitude": 1,
                "altitude_accuracy": 1,
                "radio": RADIO_TYPE[odict['radio']],
                "cell": cell_data}
        items['items'].append(data)
    print json.dumps(items)
