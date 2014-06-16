from ichnaea.tests.base import TestCase
from ichnaea.service.base import rate_limit
import time


class TestLimiter(TestCase):
    def test_limiter_maxrequests(self):
        f, a = 'func_a', 'key_b'
        maxreq = 5
        expire = 1
        for i in range(5):
            self.assertFalse(rate_limit(f, a, maxreq, expire))
            time.sleep(0.1)
        self.assertTrue(rate_limit(f, a, maxreq, expire))

    def test_limiter_expiry(self):
        f, a = 'func_c', 'key_d'
        maxreq = 100
        expire = 1
        self.assertFalse(rate_limit(f, a, maxreq, expire))
        time.sleep(1)
        self.assertFalse(rate_limit(f, a, maxreq, expire))
