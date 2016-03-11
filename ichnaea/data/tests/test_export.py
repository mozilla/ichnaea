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
        self.celery_app.export_queues = self.export_queues = configure_export(
            self.redis_client, config)
        ApiKeyFactory(valid_key='test2')
        self.session.flush()

    def test_enqueue_reports(self):
        self.add_reports(3)
        self.add_reports(1, api_key='test2')
        self.add_reports(1, api_key=None)

        for queue_key, num in [
                ('queue_export_test', 5),
                ('queue_export_everything', 5),
                ('queue_export_no_test', 2)]:
            self.assertEqual(self.export_queues[queue_key].size(), num)

    def test_one_queue(self):
        self.add_reports(3)
        schedule_export_reports.delay().get()

        # data from one queue was processed
        for queue_key, num in [
                ('queue_export_test', 0),
                ('queue_export_everything', 3),
                ('queue_export_no_test', 0)]:
            self.assertEqual(self.export_queues[queue_key].size(), num)

    def test_one_batch(self):
        self.add_reports(5)
        schedule_export_reports.delay().get()
        self.assertEqual(self.export_queues['queue_export_test'].size(), 2)

    def test_multiple_batches(self):
        self.add_reports(10)
        schedule_export_reports.delay().get()
        self.assertEqual(self.export_queues['queue_export_test'].size(), 1)
