import unittest
from webtest import TestApp
from ichnaea import main


class TestWorker(unittest.TestCase):

    def test_async_measure(self):
        try:
            import redis
        except ImportError:
            return

        global_config = {}
        app = main(global_config, celldb='sqlite://', measuredb='sqlite://',
                   async=True, **{'redis.host': '127.0.0.1',
                                  'redis.port': '6379'})
        app = TestApp(app)

        cell_data = [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]
        res = app.post_json('/v1/location/12.345678/23.456789',
                            {"cell": cell_data}, status=204)
        self.assertEqual(res.body, '')
