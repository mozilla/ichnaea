import colander

from ichnaea.api.exceptions import LocationNotFoundV1
from ichnaea.api.locate.locate_v1.schema import LocateV1Schema
from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateErrorTest,
    CommonLocateTest,
    CommonPositionTest,
)
from ichnaea.tests.base import (
    AppTestCase,
    TestCase,
)
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)


class TestSchema(TestCase):

    def test_empty(self):
        schema = LocateV1Schema()
        data = schema.deserialize({})
        self.assertEqual(data, {'cell': (), 'fallbacks': None, 'wifi': ()})

    def test_empty_cell_entry(self):
        schema = LocateV1Schema()
        data = schema.deserialize({'cell': [{}]})
        self.assertTrue('cell' in data)

    def test_wrong_cell_data(self):
        schema = LocateV1Schema()
        with self.assertRaises(colander.Invalid):
            schema.deserialize(
                {'cell': [{'mcc': 'a', 'mnc': 2, 'lac': 3, 'cid': 4}]})


class LocateV1Base(BaseLocateTest, AppTestCase):

    url = '/v1/search'
    metric = 'search'
    metric_type = 'locate'
    metric_url = 'request.v1.search'
    not_found = LocationNotFoundV1

    @property
    def ip_response(self):
        london = self.geoip_data['London']
        return {
            'status': 'ok',
            'lat': london['latitude'],
            'lon': london['longitude'],
            'accuracy': london['accuracy'],
            'fallback': 'ipf',
        }

    def check_model_response(self, response, model,
                             country=None, fallback=None, **kw):
        expected_names = set(['status', 'lat', 'lon', 'accuracy'])

        expected = super(LocateV1Base, self).check_model_response(
            response, model,
            country=country,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        self.assertEqual(data['status'], 'ok')
        self.assertAlmostEquals(data['lat'], expected['lat'])
        self.assertAlmostEquals(data['lon'], expected['lon'])
        self.assertAlmostEqual(data['accuracy'], expected['accuracy'])
        if fallback is not None:
            self.assertEqual(data['fallback'], fallback)

    def model_query(self, cells=(), wifis=()):
        query = {}
        if cells:
            query['cell'] = []
            for cell in cells:
                cell_query = {
                    'radio': cell.radio.name,
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
                query['wifi'].append({
                    'key': wifi.key,
                })
        return query


class TestView(LocateV1Base, CommonLocateTest, CommonPositionTest):

    def test_cell(self):
        cell = CellFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['radio'] = cell.radio.name
        query['cell'][0]['signal'] = -70
        query['cell'][0]['ta'] = 1

        res = self._call(body=query)
        self.check_model_response(res, cell)

        self.check_stats(
            timer=[self.metric_url],
            counter=[self.metric + '.api_key.test',
                     self.metric_type + '.result.test.all.medium.hit',
                     self.metric_type + '.source.test.all.internal.medium.hit',
                     self.metric_url + '.200'])

    def test_wifi(self):
        wifi = WifiFactory()
        offset = 0.0001
        wifis = [
            wifi,
            WifiFactory(lat=wifi.lat + offset),
            WifiFactory(lat=wifi.lat + offset * 2),
            WifiFactory(lat=None, lon=None),
        ]
        self.session.flush()

        query = self.model_query(wifis=wifis)
        wifi_query = query['wifi']
        wifi_query[0]['channel'] = 6
        wifi_query[1]['frequency'] = 2437
        wifi_query[2]['signal'] = -77
        wifi_query[3]['signalToNoiseRatio'] = 13

        res = self._call(body=query)
        self.check_model_response(res, wifi, lat=wifi.lat + offset)

        self.check_stats(counter=[
            self.metric + '.api_key.test',
            self.metric_type + '.result.test.all.high.hit',
            self.metric_type + '.source.test.all.internal.high.hit'])


class TestError(LocateV1Base, CommonLocateErrorTest):

    def test_database_error(self):
        super(TestError, self).test_database_error(db_errors=5)
