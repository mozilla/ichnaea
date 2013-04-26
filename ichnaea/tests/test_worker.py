import unittest
from webtest import TestApp

from ichnaea import main
from ichnaea.worker import _get_db


class TestWorker(unittest.TestCase):

    def test_async_measure(self):
        try:
            import redis        # NOQA
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
            res = app.post_json('/v1/submit', {"lat": 12.345678,
                                               "lon": 23.456789,
                                               "cell": cell_data}, status=204)
        finally:
            BasePipeline.execute = old

        self.assertEqual(res.body, '')

    def test_get_db(self):
        db = _get_db('sqlite:///:memory:')
        self.assertTrue(db is _get_db('sqlite:///:memory:'))
