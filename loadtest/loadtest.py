from loads.case import TestCase
import binascii
import os
import os.path
import random
import json
import pickle

# TODO: grab these args from command line
TESTING_AP_SUBSET = TESTING_CELL_SUBSET = 100


def random_ap():
    key = binascii.b2a_hex(os.urandom(15))[:12]
    key = ':'.join(key[i:i+2] for i in range(0, len(key), 2))
    return {"key": key,
            "channel": random.randint(0, 12),
            "frequency": random.randint(0, 5000),
            "channel": random.randint(1, 12),
            "signal": random.randint(-50, 0)}


def random_cell():
    return {'cid': random.randint(0, 20000),
            'mnc': random.randint(0, 5),
            'lac': random.randint(0, 5),
            'mcc': random.randint(0, 5),
            'radio': random.randint(0, 3),
            }


def generate_data():
    if not os.path.isfile('tower.pickle') or not os.path.isfile('ap.pickle'):
        tower_data = {}
        ap_data = {}
        for i in range(TESTING_CELL_SUBSET):
            lat = random.randint(-900000000, 900000000) / ((10**7)*1.0)
            lon = random.randint(-900000000, 900000000) / ((10**7)*1.0)
            tower_data[(lat, lon)] = []
            ap_data[(lat, lon)] = []

            for x in range(random.randint(1, 20)):
                rcell = random_cell()
                tower_data[(lat, lon)].append({"radio": rcell['radio'],
                                               "mcc": rcell['mcc'],
                                               "mnc": rcell['mnc'],
                                               "lac": rcell['lac'],
                                               "cid": rcell['cid']})

            # Generate upto 20 cells per lat/lon
            for x in range(random.randint(1, 20)):
                rapp = random_ap()
                ap_data[(lat, lon)].append({"key": rapp['key']})

        open('tower.pickle', 'w').write(pickle.dumps(tower_data))
        open('ap.pickle', 'w').write(pickle.dumps(ap_data))
    else:
        ap_data = pickle.load(open('ap.pickle'))
        tower_data = pickle.load(open('tower.pickle'))

    return tower_data, ap_data


class TestIchnaea(TestCase):
    def setUp(self):
        self.TOWER_DATA, self.AP_DATA = generate_data()

    def test_submit_cell_data(self):
        """
        This iterates over all generated cell data and submits it in
        batches
        """
        for (lat, lon) in self.TOWER_DATA:
            cells = []
            for cell_data in self.TOWER_DATA[(lat, lon)]:
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
            res = self.session.post('http://localhost:7001/v1/submit', blob)
            self.assertEqual(res.status_code, 204)

    def test_submit_ap_data(self):
        """
        This iterates over all generated cell data and submits it in
        batches
        """
        aps = []
        for (lat, lon), ap_data in self.AP_DATA.items():
            jdata = {"items": [{"lat": lat,
                        "lon": lon,
                        "accuracy": 17,
                        "wifi": ap_data}]}
            blob = json.dumps(jdata)
            res = self.session.post('http://localhost:7001/v1/submit', blob)
            self.assertEqual(res.status_code, 204)

    def test_submit_mixed_data(self):
        aps = []
        for (lat, lon), ap_data in self.AP_DATA.items():
            cells = []
            for cell_data in self.TOWER_DATA[(lat, lon)]:
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
            res = self.session.post('http://localhost:7001/v1/submit', blob)
            self.assertEqual(res.status_code, 204)

    def test_search_wifi(self):
        # Grab 3 keys for a lat lon
        for (lat, lon), ap_data in self.AP_DATA.items():
            expected_lat = int(lat * 1000)
            expected_lon = int(lon * 1000)
            if len(ap_data) >= 3:
                jdata = json.dumps({'wifi': ap_data[:3]})
                res = self.session.post('http://localhost:7001/v1/search?key=test', jdata)

                self.assertEqual(res.status_code, 200)
                jdata = json.loads(res.content)
                actual_lat = int(jdata['lat']*1000)
                actual_lon = int(jdata['lon']*1000)
                self.assertEquals(actual_lat, expected_lat)
                self.assertEquals(actual_lon, expected_lon)


    def test_search_cell(self):
        for (lat, lon), ap_data in self.AP_DATA.items():
            expected_lat = int(lat * 1000)
            expected_lon = int(lon * 1000)
            if len(ap_data) >= 3:
                jdata = json.dumps({'wifi': ap_data[:3]})
                res = self.session.post('http://localhost:7001/v1/search?key=test', jdata)

                self.assertEqual(res.status_code, 200)
                jdata = json.loads(res.content)
                actual_lat = int(jdata['lat']*1000)
                actual_lon = int(jdata['lon']*1000)
                self.assertEquals(actual_lat, expected_lat)
                self.assertEquals(actual_lon, expected_lon)
