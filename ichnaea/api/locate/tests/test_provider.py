from ichnaea.api.locate.location import (
    EmptyLocation,
    Country,
    Position,
)
from ichnaea.api.locate.provider import Provider
from ichnaea.api.locate.query import Query
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import ApiKeyFactory


class DummyModel(object):

    def __init__(self, lat=None, lon=None, accuracy=None,
                 alpha2=None, name=None, ip=None):
        self.lat = lat
        self.lon = lon
        self.range = accuracy
        self.alpha2 = alpha2
        self.name = name
        self.ip = ip


class ProviderTest(ConnectionTestCase):

    settings = {}

    class TestProvider(Provider):
        location_type = Position
        log_name = 'test'

    def setUp(self):
        super(ProviderTest, self).setUp()
        self.api_key = ApiKeyFactory(shortname='test')
        self.api_name = 'm'

        self.provider = self.TestProvider(
            geoip_db=self.geoip_db,
            raven_client=self.raven_client,
            redis_client=self.redis_client,
            settings=self.settings,
        )

    def model_query(self, cells=(), wifis=(), geoip=False,
                    fallbacks=None, api_key=None):
        query = {}

        if cells:
            query['cell'] = []
            for cell in cells:
                cell_query = {
                    'radio': cell.radio,
                    'mcc': cell.mcc,
                    'mnc': cell.mnc,
                    'lac': cell.lac,
                }
                if getattr(cell, 'cid', None) is not None:
                    cell_query['cid'] = cell.cid
                query['cell'].append(cell_query)

        if wifis:
            query['wifi'] = []
            for wifi in wifis:
                query['wifi'].append({'key': wifi.key})

        if geoip:
            query['geoip'] = geoip

        if fallbacks:
            query['fallbacks'] = fallbacks

        return Query(
            fallback=query.get('fallbacks'),
            geoip=query.get('geoip'),
            cell=query.get('cell'),
            wifi=query.get('wifi'),
            api_key=api_key or self.api_key,
            api_name=self.api_name,
            session=self.session,
            stats_client=self.stats_client,
        )

    def check_model_location(self, location, model, used=None, **kw):
        type_ = self.TestProvider.location_type
        if used is None:
            if model is None:
                self.assertFalse(location.query_data)
            else:
                self.assertTrue(location.query_data)
        else:
            self.assertIs(location.query_data, used)

        if not model:
            self.assertFalse(location.found())
            self.assertEqual(type(location), type_)
            return

        if type_ is Position:
            check_func = self.assertAlmostEqual
            expected = {
                'lat': kw.get('lat', model.lat),
                'lon': kw.get('lon', model.lon),
                'accuracy': kw.get('accuracy', model.range),
            }
        elif type_ is Country:
            check_func = self.assertEqual
            expected = {
                'country_code': model.alpha2,
                'country_name': model.name,
            }

        self.assertTrue(location.found())
        self.assertEqual(type(location), type_)
        for key, value in expected.items():
            check_func(getattr(location, key), value)

    def check_should_locate(self, query, should, location=None):
        if location is None:
            location = EmptyLocation()
        self.assertIs(self.provider.should_locate(query, location), should)


class GeoIPProviderTest(ProviderTest):

    @classmethod
    def setUpClass(cls):
        super(GeoIPProviderTest, cls).setUpClass()
        bhutan = cls.geoip_data['Bhutan']
        cls.bhutan_model = DummyModel(
            lat=bhutan['latitude'],
            lon=bhutan['longitude'],
            accuracy=bhutan['accuracy'],
            alpha2=bhutan['country_code'],
            name=bhutan['country_name'],
            ip=bhutan['ip'])
        london = cls.geoip_data['London']
        cls.london_model = DummyModel(
            lat=london['latitude'],
            lon=london['longitude'],
            accuracy=london['accuracy'],
            alpha2=london['country_code'],
            name=london['country_name'],
            ip=london['ip'])


class TestProvider(ProviderTest):

    def test_log_hit(self):
        query = self.model_query()
        self.provider.log_hit(query)
        self.check_stats(counter=[
            'm.test_hit',
        ])

    def test_log_success(self):
        query = self.model_query()
        self.provider.log_success(query)
        self.check_stats(counter=[
            'm.api_log.test.test_hit',
        ])

    def test_log_failure(self):
        query = self.model_query()
        self.provider.log_failure(query)
        self.check_stats(counter=[
            'm.api_log.test.test_miss',
        ])

    def test_should_locate_is_true_if_no_fallback_set(self):
        query = self.model_query(fallbacks={})
        self.check_should_locate(query, True)

    def test_should_not_locate_if_fallback_field_is_set(self):
        self.provider.fallback_field = 'ipf'
        query = self.model_query(fallbacks={'ipf': False})
        self.check_should_locate(query, False)

    def test_should_locate_if_a_different_fallback_field_is_set(self):
        self.provider.fallback_field = 'ipf'
        query = self.model_query(fallbacks={'invalid': False})
        self.check_should_locate(query, True)

    def test_should_locate_ignore_invalid_values(self):
        self.provider.fallback_field = 'ipf'
        query = self.model_query(fallbacks={'ipf': 'asdf'})
        self.check_should_locate(query, True)
