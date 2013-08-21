from unittest2 import TestCase


class TestWorkerConfig(TestCase):

    def _get_target(self):
        from ichnaea.worker import celery
        return celery

    def test_config(self):
        celery = self._get_target()
        self.assertTrue(celery.conf['CELERY_ALWAYS_EAGER'])
        self.assertEqual(celery.conf['CELERY_RESULT_BACKEND'], 'database')
