from ichnaea.locate.location_provider import (
    AbstractLocationProvider,
    AbstractCellLocationProvider,
)
from ichnaea.models.cell import (
    Cell,
    CellArea,
    CellKey,
    Radio,
)
from ichnaea.tests.base import (
    BRAZIL_MCC,
    BHUTAN_MCC,
    DBTestCase,
    FRANCE_MCC,
    FREMONT_LAT,
    FREMONT_LON,
    GB_LAT,
    GB_LON,
    GB_MCC,
    GeoIPIsolation,
    PARIS_LAT,
    PARIS_LON,
    PORTO_ALEGRE_LAT,
    PORTO_ALEGRE_LON,
    SAO_PAULO_LAT,
    SAO_PAULO_LON,
    USA_MCC,
    VIVO_MNC,
)
from ichnaea.locate.location import PositionLocation


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


class TestAbstractCellLocationProvider(DBTestCase):

    default_session = 'db_rw_session'

    def setUp(self):
        super(TestAbstractCellLocationProvider, self).setUp()

        class TestProvider(AbstractCellLocationProvider):
            model = Cell
            location_type = PositionLocation
            log_name = 'test'
            data_field = 'cell'

        self.test_class = TestProvider
        self.test_instance = TestProvider(
            self.session,
            api_key_log=True,
            api_key_name='test',
            api_name='m',
        )

    def _make_query(self, data=None, client_addr=None,
                    api_key_log=False, api_key_name='test'):
        if data is None:
            data = {'geoip': None, 'cell': [], 'wifi': []}
        if client_addr:
            data['geoip'] = client_addr
        return self.test_class(
            self.session,
            api_key_log=api_key_log,
            api_key_name=api_key_name,
            api_name='m',
        ).locate(data)

    def test_locate_searches_provided_model(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(Cell(lat=GB_LAT, lon=GB_LON, range=6000,
                              radio=Radio.gsm, cid=1, **cell_key))
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]},
            api_key_log=True)
        self.assertEqual(type(result), PositionLocation)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.accuracy, 6000)
