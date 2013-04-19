from unittest import TestCase
from webtest import TestApp

from ichnaea import main


class TestHeartbeat(TestCase):

    def setUp(self):
        global_config = {}
        wsgiapp = main(global_config, database='sqlite://')
        self.app = TestApp(wsgiapp)

    def test_ok(self):
        res = self.app.get('/__heartbeat__')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.body, '{"status": "OK"}')
