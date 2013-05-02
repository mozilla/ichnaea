import unittest
import time

from redis.client import BasePipeline
from webtest import TestApp

from ichnaea import main
from ichnaea.worker import _get_db


class TestWorker(unittest.TestCase):

    def _make_one(self, **kw):
        kw['redis.host'] = '127.0.0.1'
        kw['redis.port'] = -1
        app = main({}, celldb='sqlite://', measuredb='sqlite://',
                   async=True, **kw)
        return TestApp(app)

    def test_get_db(self):
        db = _get_db('sqlite:///:memory:')
        self.assertTrue(db is _get_db('sqlite:///:memory:'))

    def test_async_measure(self):
        app = self._make_one(batch_size=10)
        cell_data = [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]
        old = BasePipeline.execute
        called = [0]

        def _execute(*args, **kw):
            called[0] += 1

        BasePipeline.execute = _execute

        try:
            for i in range(21):
                res = app.post_json(
                    '/v1/submit', {"items": [{"lat": 12.345678,
                                              "lon": 23.456789,
                                              "cell": cell_data}]},
                    status=204)
        finally:
            BasePipeline.execute = old

        self.assertEqual(res.body, '')

        # 2 batches of 10
        self.assertEqual(called[0], 2)

    def test_async_old_batch(self):
        app = self._make_one(batch_size=10, batch_age=0.5)
        cell_data = [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]
        old = BasePipeline.execute
        called = [0]

        def _execute(*args, **kw):
            called[0] += 1

        BasePipeline.execute = _execute

        try:
            for i in range(4):
                res = app.post_json(
                    '/v1/submit', {"items": [{"lat": 12.345678,
                                              "lon": 23.456789,
                                              "cell": cell_data}]},
                    status=204)
                time.sleep(.3)
        finally:
            BasePipeline.execute = old

        self.assertEqual(res.body, '')

        # 1 batches of 2
        self.assertEqual(called[0], 1)
