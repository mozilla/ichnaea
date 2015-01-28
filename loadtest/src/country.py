from loads.case import TestCase


class TestCountry(TestCase):

    def setUp(self):
        self.target = self.app.server_url + '/v1/country?key=test'
        self.headers = {}
        if '127.0.0.1' in self.target or 'localhost' in self.target:
            self.headers['X-Forwarded-For'] = '81.2.69.192'

    def test_geoip(self):
        res = self.session.post(self.target, json={}, headers=self.headers)
        self.assertEqual(res.status_code, 200)
