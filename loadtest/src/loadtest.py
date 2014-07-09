from ConfigParser import SafeConfigParser
from loads.case import TestCase
import binascii
import json
import os
import os.path
import random

RADIO_TYPE = {
    '': -1,
    'gsm': 0,
    'cdma': 1,
    'umts': 2,
    'lte': 3,
}
RADIO_MAP = dict([(v, k) for k, v in RADIO_TYPE.items() if k != ''])

INVALID_WIFI_KEY = 'aa:aa:aa:aa:aa:aa'

random.seed(32314)

cfg = SafeConfigParser()
cfg.read(os.path.join('src', 'ichnaea.ini'))

TOWER_FILE = os.path.join('src', 'tower.json')
AP_FILE = os.path.join('src', 'ap.json')
HOST = 'https://' + cfg.get('loadtest', 'WEBAPP_HOST')

TESTING_AP_SUBSET = TESTING_CELL_SUBSET = 10000


def rand_bytes(length):
    return ''.join(chr(random.randint(0, 255)) for _ in range(length))


def random_ap():
    for channel in range(1, 12):
        for frequency in range(1, 5000):
            for signal in range(-50, 0):
                key = binascii.b2a_hex(rand_bytes(15))[:12]
                key = ':'.join(key[i:i + 2] for i in range(0, len(key), 2))
                yield {"key": key,
                       "channel": random.randint(1, 12),
                       "frequency": random.randint(0, 5000),
                       "signal": random.randint(-50, 0)}


def random_cell():
    # don't test cdma, as that would complicate setting up the
    # top-level radio field in the JSON dicts
    for radio in (0, 2, 3):
        for mcc in range(1, 5):
            for mnc in range(1, 5):
                for cid in range(1, 20000):
                    for lac in range(1, 5):
                        yield {'cid': cid,
                               'mnc': mnc,
                               'lac': lac,
                               'mcc': mcc,
                               'radio': radio}


def generate_data():
    if not os.path.isfile(TOWER_FILE) or not os.path.isfile(AP_FILE):
        tower_data = JSONTupleKeyedDict()
        ap_data = JSONTupleKeyedDict()
        cell_gen = random_cell()
        wifi_gen = random_ap()
        for i in range(TESTING_CELL_SUBSET):
            lat = random.randint(-900000000, 900000000) / ((10 ** 7) * 1.0)
            lon = random.randint(-900000000, 900000000) / ((10 ** 7) * 1.0)
            tower_data[(lat, lon)] = []
            ap_data[(lat, lon)] = []

            for x in range(random.randint(1, 20)):
                rcell = cell_gen.next()
                data = {"radio": rcell['radio'],
                        "mcc": rcell['mcc'],
                        "mnc": rcell['mnc'],
                        "lac": rcell['lac'],
                        "cid": rcell['cid']}
                if data not in tower_data[(lat, lon)]:
                    tower_data[(lat, lon)].append(data)

            for x in range(random.randint(1, 20)):
                rapp = wifi_gen.next()
                ap_data[(lat, lon)].append({"key": rapp['key']})

        with open(TOWER_FILE, 'w') as f:
            f.write(json.dumps(tower_data, cls=LocationDictEncoder))
        with open(AP_FILE, 'w') as f:
            f.write(json.dumps(ap_data, cls=LocationDictEncoder))
    else:
        ap_data = json.load(open(AP_FILE),
                            object_hook=JSONLocationDictDecoder)
        tower_data = json.load(open(TOWER_FILE),
                               object_hook=JSONLocationDictDecoder)

    return tower_data.items(), ap_data.items()


class TestIchnaea(TestCase):
    TOWER_DATA = None
    AP_DATA = None

    def setUp(self):
        if self.TOWER_DATA is None:
            self.TOWER_DATA, self.AP_DATA = generate_data()

    def test_submit_cell_data(self):
        """
        This iterates over all generated cell data and submits it in
        batches
        """
        (lat, lon), all_cell_data = random.choice(self.TOWER_DATA)

        cells = []

        for cell_data in all_cell_data:
            cells.append({"radio": RADIO_MAP.get(cell_data['radio'], ''),
                          "mcc": cell_data['mcc'],
                          "mnc": cell_data['mnc'],
                          "lac": cell_data['lac'],
                          "cid": cell_data['cid']})

        json_data = {"items": [{"lat": lat,
                                "lon": lon,
                                "accuracy": 10,
                                "altitude": 1,
                                "altitude_accuracy": 7,
                                "radio": "gsm",
                                "cell": cells}]}
        blob = json.dumps(json_data)
        res = self.session.post(HOST + '/v1/submit?key=test', blob)
        self.assertEqual(res.status_code, 204)

    def test_submit_ap_data(self):
        """
        This iterates over all generated wifi access point data and
        submits it in batches
        """
        (lat, lon), ap_data = random.choice(self.AP_DATA)
        jdata = {"items": [{"lat": lat,
                            "lon": lon,
                            "accuracy": 17,
                            "wifi": ap_data}]}
        blob = json.dumps(jdata)
        res = self.session.post(HOST + '/v1/submit?key=test', blob)
        self.assertEqual(res.status_code, 204)

    def test_submit_mixed_data(self):
        (lat, lon), cell_info = random.choice(self.TOWER_DATA)
        cells = []
        for cell_data in cell_info:
            cells.append({"radio": RADIO_MAP.get(cell_data['radio'], ''),
                          "mcc": cell_data['mcc'],
                          "mnc": cell_data['mnc'],
                          "lac": cell_data['lac'],
                          "cid": cell_data['cid']})

        ap_data = [v for k, v in self.AP_DATA if k == (lat, lon)][0]
        jdata = {"items": [{"lat": lat,
                            "lon": lon,
                            "accuracy": 10,
                            "altitude": 1,
                            "altitude_accuracy": 7,
                            "radio": "gsm",
                            "cell": cells,
                            "wifi": ap_data,
                            }]
                 }

        blob = json.dumps(jdata)
        res = self.session.post(HOST + '/v1/submit?key=test', blob)
        self.assertEqual(res.status_code, 204)

    def test_search_wifi(self):
        """
        Grab 3 keys for a lat lon
        """
        (lat, lon), ap_data = random.choice(self.AP_DATA)

        expected_lat = int(lat * 1000)
        expected_lon = int(lon * 1000)
        if len(ap_data) >= 3:
            wifi_data = ap_data[:3]
            if random.random() >= 0.5:
                # Throw in some garbage
                wifi_data.append({'key': INVALID_WIFI_KEY})
            jdata = json.dumps({'wifi': wifi_data})
            res = self.session.post(HOST + '/v1/search?key=test', jdata)

            self.assertEqual(res.status_code, 200)
            jdata = json.loads(res.content)
            if jdata['status'] != 'not_found':
                actual_lat = int(jdata['lat'] * 1000)
                actual_lon = int(jdata['lon'] * 1000)
                self.assertEquals(actual_lat, expected_lat)
                self.assertEquals(actual_lon, expected_lon)

    def test_search_cell(self):
        (lat, lon), all_cells = random.choice(self.TOWER_DATA)

        expected_lat = int(lat * 1000)
        expected_lon = int(lon * 1000)

        query_data = {"radio": '', "cell": []}
        for cell_data in all_cells:
            radio_name = RADIO_MAP[cell_data['radio']]
            if query_data['radio'] == '':
                query_data['radio'] = radio_name
            query_data['cell'].append(dict(radio=radio_name,
                                           cid=cell_data['cid'],
                                           mcc=cell_data['mcc'],
                                           mnc=cell_data['mnc'],
                                           lac=cell_data['lac']))
            jdata = json.dumps(query_data)
            res = self.session.post(HOST + '/v1/search?key=test', jdata)
            self.assertEqual(res.status_code, 200)
            jdata = json.loads(res.content)
            if jdata['status'] != 'not_found':
                actual_lat = int(jdata['lat'] * 1000)
                actual_lon = int(jdata['lon'] * 1000)
                self.assertEquals(actual_lat, expected_lat)
                self.assertEquals(actual_lon, expected_lon)


class JSONTupleKeyedDict(dict):
    pass


class LocationDictEncoder(json.JSONEncoder):
    def iterencode(self, obj, *args, **kwargs):
        if isinstance(obj, JSONTupleKeyedDict):
            tmp = {'__JSONTupleKeyedDict__': True, 'dict': {}}
            for k, v in obj.items():
                tmp['dict'][json.dumps(k)] = v
        return json.JSONEncoder.iterencode(self, tmp, *args, **kwargs)


def JSONLocationDictDecoder(dct):
    if '__JSONTupleKeyedDict__' in dct:
        tmp = {}
        for k, v in dct['dict'].items():
            tmp[tuple(json.loads(k))] = v
        return tmp
    return dct
