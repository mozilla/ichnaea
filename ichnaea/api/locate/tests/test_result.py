from ichnaea.api.locate.constants import (
    DataAccuracy,
    DataSource,
)
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import (
    Position,
    PositionResultList,
    Region,
    RegionResultList,
    Result,
    ResultList,
)
from ichnaea.models import encode_mac
from ichnaea.tests.factories import WifiShardFactory


class TestResult(object):

    def test_repr(self):
        result = Result(region_code='DE', lat=1.0)
        rep = repr(result)
        assert rep.startswith('Result')
        assert 'DE' not in rep
        assert '1.0' not in rep

    def test_data_accuracy(self):
        assert Result().data_accuracy is DataAccuracy.none

    def test_used_networks(self):
        wifi = WifiShardFactory.build()
        network = ('wifi', encode_mac(wifi.mac), True)
        assert Result().used_networks == []
        assert Result(used_networks=[network]).used_networks == [network]


class TestPosition(object):

    def test_repr(self):
        position = Position(lat=1.0, lon=-1.1, accuracy=100.0, score=2.0)
        rep = repr(position)
        assert rep.startswith('Position')
        assert '1.0' in rep
        assert '-1.1' in rep
        assert '100.0' in rep
        assert position.score == 2.0

    def test_json(self):
        assert (Position().json() ==
                {'position': {'source': 'query'}})
        assert (Position(lat=1.0, lon=1.0, accuracy=2.0).json() ==
                {'position': {'latitude': 1.0, 'longitude': 1.0,
                              'accuracy': 2.0, 'source': 'query'}})

    def test_data_accuracy(self):
        def check(accuracy, expected):
            pos = Position(lat=1.0, lon=1.0, accuracy=accuracy)
            assert pos.data_accuracy is expected

        check(None, DataAccuracy.none)
        check(0.0, DataAccuracy.high)
        check(100, DataAccuracy.high)
        check(20000.0, DataAccuracy.medium)
        check(10 ** 6, DataAccuracy.low)


class TestRegion(object):

    def test_repr(self):
        region = Region(region_code='DE', region_name='Germany',
                        accuracy=100.0, score=2.0)
        rep = repr(region)
        assert rep.startswith('Region')
        assert 'DE' in rep
        assert 'Germany' in rep
        assert region.score == 2.0

    def test_data_accuracy(self):
        assert Region().data_accuracy is DataAccuracy.none
        region = Region(
            region_code='DE', region_name='Germany', accuracy=100000.0)
        assert region.data_accuracy is DataAccuracy.low
        region = Region(
            region_code='VA', region_name='Holy See', accuracy=1000.0)
        assert region.data_accuracy is DataAccuracy.medium


class TestResultList(object):

    def _make_result(self):
        return Position(lat=1.0, lon=1.0, accuracy=10.0,
                        score=0.5, source=DataSource.internal)

    def test_init(self):
        results = ResultList(self._make_result())
        assert len(results) == 1

    def test_repr(self):
        results = ResultList([self._make_result(), self._make_result()])
        rep = repr(results)
        assert rep.startswith('ResultList:')
        assert 'Position<' in rep
        assert 'lat:1.0' in rep
        assert 'lon:1.0' in rep
        assert 'accuracy:10.0' in rep
        assert 'score:0.5' in rep

    def test_add(self):
        results = ResultList()
        results.add(self._make_result())
        assert len(results) == 1

    def test_add_many(self):
        results = ResultList(self._make_result())
        results.add((self._make_result(), self._make_result()))
        assert len(results) == 3

    def test_len(self):
        results = ResultList()
        results.add(self._make_result())
        results.add(self._make_result())
        assert len(results) == 2

    def test_getitem(self):
        result = self._make_result()
        results = ResultList()
        results.add(result)
        assert results[0] == result

    def test_iterable(self):
        result = self._make_result()
        results = ResultList()
        results.add(result)
        results.add(result)
        for res in results:
            assert res == result


class TestPositionResultList(object):

    def test_repr(self):
        assert repr(PositionResultList()).startswith('PositionResultList:')

    def test_best_empty(self):
        assert PositionResultList().best() is None

    def test_best(self):
        gb1 = Position(lat=51.5, lon=-0.1, accuracy=100000.0, score=0.6)
        gb2 = Position(lat=51.5002, lon=-0.1, accuracy=10000.0, score=1.5)
        gb3 = Position(lat=51.7, lon=-0.1, accuracy=1000.0, score=5.0)
        bt1 = Position(lat=27.5002, lon=90.5, accuracy=1000.0, score=0.5)
        bt2 = Position(lat=27.5, lon=90.5, accuracy=2000.0, score=2.0)
        bt3 = Position(lat=27.7, lon=90.7, accuracy=500.0, score=5.0)
        bt4 = Position(lat=27.9, lon=90.7, accuracy=300.0, score=5.0)

        # single result works
        assert PositionResultList([gb1]).best().lat == 51.5

        # the lowest accuracy result from the best cluster wins
        assert PositionResultList([bt1, bt2]).best().lat == 27.5002
        assert PositionResultList([gb1, bt2]).best().lat == 27.5
        assert PositionResultList([gb1, gb2, bt2]).best().lat == 51.5002
        assert PositionResultList([gb1, gb3, bt1, bt2]).best().lat == 51.7
        assert PositionResultList([gb1, gb2, bt2, bt3]).best().lat == 27.7

        # break tie by accuracy
        assert PositionResultList([gb3, bt3]).best().lat == 27.7
        assert PositionResultList([bt3, bt4]).best().lat == 27.9

    def test_satisfies(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi_query = [{'macAddress': wifi.mac} for wifi in wifis]
        positions = PositionResultList([
            Position(lat=1.0, lon=1.0, accuracy=100.0, score=0.5),
            Position(lat=1.0, lon=1.0, accuracy=10000.0, score=0.6)])
        query = Query(api_type='locate', wifi=wifi_query)
        assert positions.satisfies(query)

    def test_satisfies_empty(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi_query = [{'macAddress': wifi.mac} for wifi in wifis]
        positions = PositionResultList()
        query = Query(api_type='locate', wifi=wifi_query)
        assert not positions.satisfies(query)

    def test_satisfies_fail(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi_query = [{'macAddress': wifi.mac} for wifi in wifis]
        positions = PositionResultList(
            Position(lat=1.0, lon=1.0, accuracy=2500.0, score=2.0))
        query = Query(api_type='locate', wifi=wifi_query)
        assert not positions.satisfies(query)


class TestRegionResultList(object):

    def test_repr(self):
        assert repr(RegionResultList()).startswith('RegionResultList:')

    def test_best_empty(self):
        assert RegionResultList().best() is None

    def test_best(self):
        us1 = Region(region_code='US', region_name='us',
                     accuracy=200000.0, score=3.0, source=DataSource.geoip)
        us2 = Region(region_code='US', region_name='us',
                     accuracy=200000.0, score=3.0, source=DataSource.geoip)
        gb1 = Region(region_code='GB', region_name='gb',
                     accuracy=100000.0, score=5.0, source=DataSource.geoip)
        gb2 = Region(region_code='GB', region_name='gb',
                     accuracy=100000.0, score=3.0, source=DataSource.geoip)

        # highest combined score wins
        assert RegionResultList([us1, gb1]).best().region_code == 'GB'
        assert RegionResultList([us1, gb1, us2]).best().region_code == 'US'

        # break tie by accuracy
        assert RegionResultList([us1, gb2]).best().region_code == 'US'

    def test_satisfies(self):
        regions = RegionResultList(Region(
            region_code='DE', region_name='Germany', accuracy=100000.0))
        assert regions.satisfies(Query())

    def test_satisfies_fail(self):
        assert not RegionResultList().satisfies(Query())
