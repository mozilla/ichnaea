RADIO_TYPE = {
    '': -1,
    'gsm': 0,
    'cdma': 1,
    'umts': 2,
    'lte': 3,
}
from loads.case import TestCase
import binascii
import json
import os
import os.path
import pickle
import random
from ConfigParser import SafeConfigParser

cfg = SafeConfigParser()
cfg.read(os.path.join('src', 'ichnaea.ini'))

TOWER_FILE = os.path.join('src', 'tower.pickle')
AP_FILE = os.path.join('src', 'ap.pickle')
HOST = 'https://' + cfg.get('loadtest', 'WEBAPP_HOST')

TESTING_AP_SUBSET = TESTING_CELL_SUBSET = 10000


def random_ap():
    for channel in range(1, 12):
        for frequency in range(1, 5000):
            for signal in range(-50, 0):
                key = binascii.b2a_hex(os.urandom(15))[:12]
                key = ':'.join(key[i:i+2] for i in range(0, len(key), 2))
                yield {"key": key,
                       "channel": random.randint(1, 12),
                       "frequency": random.randint(0, 5000),
                       "signal": random.randint(-50, 0)}


def random_cell():
    for radio in range(0, 3):
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
        tower_data = {}
        ap_data = {}
        cell_gen = random_cell()
        wifi_gen = random_ap()
        for i in range(TESTING_CELL_SUBSET):
            lat = random.randint(-900000000, 900000000) / ((10**7)*1.0)
            lon = random.randint(-900000000, 900000000) / ((10**7)*1.0)
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

        open(TOWER_FILE, 'w').write(pickle.dumps(tower_data))
        open(AP_FILE, 'w').write(pickle.dumps(ap_data))
    else:
        ap_data = pickle.load(open(AP_FILE))
        tower_data = pickle.load(open(TOWER_FILE))

    return tower_data, ap_data


class TestIchnaea(TestCase):
    TOWER_DATA = None
    AP_DATA = None

    def setUp(self):
        if self.TOWER_DATA is None:
            self.TOWER_DATA, self.AP_DATA = generate_data()
            self.TOWER_DATA, self.AP_DATA = self.TOWER_DATA.items(), self.AP_DATA.items()

    def test_submit_cell_data(self):
        """
        This iterates over all generated cell data and submits it in
        batches
        """
        (lat, lon), all_cell_data = random.choice(self.TOWER_DATA)

        cells = []
        for cell_data in all_cell_data:
            cells.append({"radio": "umts",
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
        res = self.session.post(HOST+'/v1/submit', blob)
        self.assertEqual(res.status_code, 204)

    def test_submit_ap_data(self):
        """
        This iterates over all generated cell data and submits it in
        batches
        """
        (lat, lon), ap_data = random.choice(self.AP_DATA)
        jdata = {"items": [{"lat": lat,
                            "lon": lon,
                            "accuracy": 17,
                            "wifi": ap_data}]}
        blob = json.dumps(jdata)
        res = self.session.post(HOST+'/v1/submit', blob)
        self.assertEqual(res.status_code, 204)

    def test_submit_mixed_data(self):
        (lat, lon), ap_data = random.choice(self.AP_DATA)
        cells = []
        for cell_data in ap_data:
            cells.append({"radio": "umts",
                          "mcc": cell_data['mcc'],
                          "mnc": cell_data['mnc'],
                          "lac": cell_data['lac'],
                          "cid": cell_data['cid']})

        jdata = {"items": [{"lat": lat,
                            "lon": lon,
                            "accuracy": 10,
                            "altitude": 1,
                            "altitude_accuracy": 7,
                            "radio": "gsm",
                            "cell": cells}]}

        jdata['items'].append({"lat": lat,
                               "lon": lon,
                               "accuracy": 17,
                               "wifi": ap_data})
        blob = json.dumps(jdata)
        res = self.session.post(HOST+'/v1/submit', blob)
        self.assertEqual(res.status_code, 204)

    def test_search_wifi(self):
        """
        Grab 3 keys for a lat lon
        """
        (lat, lon), ap_data = random.choice(self.TOWER_DATA)

        expected_lat = int(lat * 1000)
        expected_lon = int(lon * 1000)
        if len(ap_data) >= 3:
            wifi_data = ap_data[:3]
            if random.random() >= 0.5:
                # Throw in some garbage
                wifi_data.append({'key': 'aa:aa:aa:aa:aa:aa'})
            jdata = json.dumps({'wifi': wifi_data})
            res = self.session.post(HOST+'/v1/search?key=test', jdata)

            self.assertEqual(res.status_code, 200)
            jdata = json.loads(res.content)
            if jdata['status'] != 'not_found':
                actual_lat = int(jdata['lat']*1000)
                actual_lon = int(jdata['lon']*1000)
                self.assertEquals(actual_lat, expected_lat)
                self.assertEquals(actual_lon, expected_lon)

    def test_search_cell(self):
        RADIO_MAP = dict([(v, k) for k, v in RADIO_TYPE.items() if k != ''])

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
            res = self.session.post(HOST+'/v1/search?key=test', jdata)
            self.assertEqual(res.status_code, 200)
            jdata = json.loads(res.content)
            if jdata['status'] != 'not_found':
                actual_lat = int(jdata['lat']*1000)
                actual_lon = int(jdata['lon']*1000)
                self.assertEquals(actual_lat, expected_lat)
                self.assertEquals(actual_lon, expected_lon)
