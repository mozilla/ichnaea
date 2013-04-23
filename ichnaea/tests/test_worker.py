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
                                  'redis.port': '-1'})
        app = TestApp(app)

        cell_data = [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]

        from redis.client import BasePipeline

        old = BasePipeline.execute

        def _execute(*args, **kw):
            pass

        BasePipeline.execute = _execute

        try:
            res = app.post_json('/v1/location/12.345678/23.456789',
                                {"cell": cell_data}, status=204)
        finally:
            BasePipeline.execute = old

        self.assertEqual(res.body, '')
