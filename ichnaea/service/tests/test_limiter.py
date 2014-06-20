from ichnaea.tests.base import TestCase
from ichnaea.service.base import rate_limit
import time

from ichnaea.tests.base import (
    _make_app,
    REDIS_URI,
    SQLURI,
)


class TestLimiter(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        settings = {
            'db_master': SQLURI,
            'db_slave': SQLURI,
            'redis_url': REDIS_URI,
            '_heka_client': None,
        }
        self.app = _make_app(**settings)
        self.registry = self.app.app.registry

    def test_limiter_maxrequests(self):
        redis_con = self.registry.redis_con
        f, a = 'func_a', 'key_b'
        maxreq = 5
        expire = 1
        for i in range(5):
            self.assertFalse(rate_limit(redis_con, f, a,
                                        maxreq=maxreq,
                                        expire=expire))
            time.sleep(0.1)
        self.assertTrue(rate_limit(redis_con, f, a,
                                   maxreq=maxreq,
                                   expire=expire))

    def test_limiter_expiry(self):
        redis_con = self.registry.redis_con
        f, a = 'func_c', 'key_d'
        maxreq = 100
        expire = 1
        self.assertFalse(rate_limit(redis_con, f, a,
                                    maxreq=maxreq,
                                    expire=expire))
        time.sleep(1)
        self.assertFalse(rate_limit(redis_con, f, a,
                                    maxreq=maxreq,
                                    expire=expire))
