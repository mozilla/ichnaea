from ichnaea.locate.location_provider import AbstractLocationProvider
from ichnaea.locate.location import PositionLocation
from ichnaea.tests.base import DBTestCase


class TestAbstractLocationProvider(DBTestCase):

    default_session = 'db_ro_session'

    def setUp(self):
        super(TestAbstractLocationProvider, self).setUp()

        class TestProvider(AbstractLocationProvider):
            location_type = PositionLocation
            log_name = 'test'

        self.test_class = TestProvider
        self.test_instance = TestProvider(
            self.session,
            api_key_log=True,
            api_key_name='test',
            api_name='m',
        )

    def test_log_hit(self):
        self.test_instance.log_hit()
        self.check_stats(
            counter=[
                'm.test_hit',
            ],
        )

    def test_log_success(self):
        self.test_instance.log_success()
        self.check_stats(
            counter=[
                'm.api_log.test.test_hit',
            ],
        )

    def test_log_failure(self):
        self.test_instance.log_failure()
        self.check_stats(
            counter=[
                'm.api_log.test.test_miss',
            ],
        )
