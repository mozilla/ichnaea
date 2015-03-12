from ichnaea.constants import (
    LAC_MIN_ACCURACY,
)
from ichnaea.locate.location_provider import (
    AbstractLocationProvider,
    AbstractCellLocationProvider,
    AbstractCellAreaLocationProvider,
)
from ichnaea.models.cell import (
    Cell,
    CellArea,
    Radio,
)
from ichnaea.tests.base import (
    DBTestCase,
    GB_LAT,
    GB_LON,
    GB_MCC,
)
from ichnaea.locate.location import PositionLocation


class AbstractLocationProviderTest(DBTestCase):

    default_session = 'db_ro_session'

    class TestProvider(AbstractLocationProvider):
        location_type = PositionLocation
        log_name = 'test'

    def setUp(self):
        super(AbstractLocationProviderTest, self).setUp()

        self.test_instance = self.TestProvider(
            self.session,
            api_key_log=True,
            api_key_name='test',
            api_name='m',
        )


class TestAbstractLocationProvider(AbstractLocationProviderTest):

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


class TestAbstractCellLocationProvider(AbstractLocationProviderTest):

    class TestProvider(AbstractCellLocationProvider):
        model = Cell
        location_type = PositionLocation
        log_name = 'test'
        data_field = 'cell'

    def test_locate_with_no_data_returns_None(self):
        location = self.test_instance.locate({})
        self.assertFalse(location.found())

    def test_locate_finds_cell_with_same_cid(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=6000,
            radio=Radio.gsm, cid=1, **cell_key))
        self.session.flush()

        location = self.test_instance.locate(
            {'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]})
        self.assertEqual(type(location), PositionLocation)
        self.assertEqual(location.lat, GB_LAT)
        self.assertEqual(location.lon, GB_LON)
        self.assertEqual(location.accuracy, 6000)

    def test_locate_fails_to_find_cell_with_wrong_cid(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=6000,
            radio=Radio.gsm, cid=1, **cell_key))
        self.session.flush()

        location = self.test_instance.locate(
            {'cell': [dict(cid=2, radio=Radio.gsm.name, **cell_key)]})
        self.assertFalse(location.found())

    def test_multiple_cells_combined(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT + 0.1, lon=GB_LON + 0.1, range=6000,
            radio=Radio.gsm, cid=1, **cell_key))
        self.session.add(self.TestProvider.model(
            lat=GB_LAT + 0.3, lon=GB_LON + 0.3, range=6000,
            radio=Radio.gsm, cid=2, **cell_key))
        self.session.flush()

        location = self.test_instance.locate({'cell': [
            dict(cid=1, radio=Radio.gsm.name, **cell_key),
            dict(cid=2, radio=Radio.gsm.name, **cell_key),
        ]})
        self.assertEqual(type(location), PositionLocation)
        self.assertEqual(location.lat, GB_LAT + 0.2)
        self.assertEqual(location.lon, GB_LON + 0.2)


class TestAbstractCellAreaLocationProvider(AbstractLocationProviderTest):

    class TestProvider(AbstractCellAreaLocationProvider):
        model = CellArea
        location_type = PositionLocation
        log_name = 'cell_lac'
        data_field = 'cell'

    def test_shortest_range_lac_used(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=25000,
            radio=Radio.gsm, lac=1, **cell_key))
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=30000,
            radio=Radio.gsm, lac=2, **cell_key))
        self.session.flush()

        location = self.test_instance.locate({'cell': [
            dict(radio=Radio.gsm.name, lac=1, cid=1, **cell_key),
            dict(radio=Radio.gsm.name, lac=2, cid=1, **cell_key),
        ]})
        self.assertEqual(type(location), PositionLocation)
        self.assertEqual(location.lat, GB_LAT)
        self.assertEqual(location.lon, GB_LON)
        self.assertEqual(location.accuracy, 25000)

    def test_minimum_range_returned(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=15000,
            radio=Radio.gsm, lac=1, **cell_key))
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=30000,
            radio=Radio.gsm, lac=2, **cell_key))
        self.session.flush()

        location = self.test_instance.locate({'cell': [
            dict(radio=Radio.gsm.name, lac=1, cid=1, **cell_key),
            dict(radio=Radio.gsm.name, lac=2, cid=1, **cell_key),
        ]})
        self.assertEqual(type(location), PositionLocation)
        self.assertEqual(location.lat, GB_LAT)
        self.assertEqual(location.lon, GB_LON)
        self.assertEqual(location.accuracy, LAC_MIN_ACCURACY)
