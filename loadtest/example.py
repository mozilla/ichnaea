from loads.case import TestCase
import json


class TestWebSite(TestCase):
    def test_submit_cell_data(self):
        cell_data = [{"radio": "umts",
                      "mcc": 123,
                      "mnc": 1,
                      "lac": 2,
                      "cid": 1234}]

        items = {"items": [{"lat": 12.3456781,
                 "lon": 23.4567892,
                 "accuracy": 10,
                 "altitude": 123,
                 "altitude_accuracy": 7,
                 "radio": "gsm",
                 "cell": cell_data}]}

        data = json.dumps(items)
        res = self.session.post('http://localhost:7001/v1/submit', data)
        self.assertEqual(res.status_code, 204)
