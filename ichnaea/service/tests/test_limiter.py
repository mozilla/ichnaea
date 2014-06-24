from ichnaea.tests.base import TestCase
from ichnaea.service.base import rate_limit
import time

from ichnaea.tests.base import (
    _make_app,
    _make_db,
    _make_redis,
)


class TestLimiter(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        db = _make_db()
        cache = _make_redis()
        self.app = _make_app(_db_master=db, _db_slave=db, _redis=cache)
        self.registry = self.app.app.registry

    def test_limiter_maxrequests(self):
        redis_client = self.registry.redis_client
        f, a = 'func_a', 'key_b'
        maxreq = 5
        expire = 1
        for i in range(5):
            self.assertFalse(rate_limit(redis_client, f, a,
                                        maxreq=maxreq,
                                        expire=expire))
            time.sleep(0.1)
        self.assertTrue(rate_limit(redis_client, f, a,
                                   maxreq=maxreq,
                                   expire=expire))

    def test_limiter_expiry(self):
        redis_client = self.registry.redis_client
        f, a = 'func_c', 'key_d'
        maxreq = 100
        expire = 1
        self.assertFalse(rate_limit(redis_client, f, a,
                                    maxreq=maxreq,
                                    expire=expire))
        time.sleep(1)
        self.assertFalse(rate_limit(redis_client, f, a,
                                    maxreq=maxreq,
                                    expire=expire))
