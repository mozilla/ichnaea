from ichnaea.async.config import configure_export
from ichnaea.config import DummyConfig
from ichnaea.data.tasks import (
    schedule_export_reports,
)
from ichnaea.data.tests.base import BaseExportTest
from ichnaea.tests.factories import (
    ApiKeyFactory,
)


class TestExporter(BaseExportTest):

    def setUp(self):
        super(TestExporter, self).setUp()
        config = DummyConfig({
            'export:test': {
                'url': None,
                'skip_keys': 'export_source',
                'batch': '3',
            },
            'export:everything': {
                'url': '',
                'batch': '5',
            },
            'export:no_test': {
                'skip_keys': 'test_1 test\ntest:-1',
                'batch': '2',
            },
            'export:invalid_ftp': {
                'url': 'ftp://127.0.0.1:9/',
                'batch': '5',
            },
            'export:invalid': {
                'url': 'no_url',
                'batch': '5',
            },
        })
        self.celery_app.export_queues = queues = configure_export(
            self.redis_client, config)
        self.test_queue_key = queues['test'].queue_key()
        ApiKeyFactory(valid_key='test2', log_submit=True)
        self.session.flush()

    def test_enqueue_reports(self):
        self.add_reports(3)
        self.add_reports(1, api_key='test2')
        self.add_reports(1, api_key=None)

        export_queues = self.celery_app.export_queues
        expected = [
            (export_queues['test'].queue_key(), 5),
            (export_queues['everything'].queue_key(), 5),
            (export_queues['no_test'].queue_key(), 2),
        ]
        for key, num in expected:
            self.assertEqual(self.queue_length(key), num)

    def test_one_queue(self):
        self.add_reports(3)
        triggered = schedule_export_reports.delay().get()
        self.assertEqual(triggered, 1)

        # data from one queue was processed
        export_queues = self.celery_app.export_queues
        expected = [
            (export_queues['test'].queue_key(), 0),
            (export_queues['everything'].queue_key(), 3),
            (export_queues['no_test'].queue_key(), 0),
        ]
        for key, num in expected:
            self.assertEqual(self.queue_length(key), num)

    def test_one_batch(self):
        self.add_reports(5)
        schedule_export_reports.delay().get()
        self.assertEqual(self.queue_length(self.test_queue_key), 2)

    def test_multiple_batches(self):
        self.add_reports(10)
        schedule_export_reports.delay().get()
        self.assertEqual(self.queue_length(self.test_queue_key), 1)
