from ichnaea.tests.base import AppTestCase


class TestHeartbeat(AppTestCase):

    def test_ok(self):
        app = self.app
        res = app.get('/__heartbeat__', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json['status'], "OK")
