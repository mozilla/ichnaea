from ichnaea.api.locate.constants import DataAccuracy
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import (
    Position,
    PositionResultList,
    Region,
    RegionResultList,
    Result,
    ResultList,
)
from ichnaea.tests.base import TestCase
from ichnaea.tests.factories import WifiShardFactory


class TestResult(TestCase):

    def test_repr(self):
        result = Result(region_code='DE', lat=1.0)
        rep = repr(result)
        self.assertTrue(rep.startswith('Result'), rep)
        self.assertFalse('DE' in rep, rep)
        self.assertFalse('1.0' in rep, rep)

    def test_data_accuracy(self):
        self.assertEqual(Result().data_accuracy, DataAccuracy.none)


class TestPosition(TestCase):

    def test_repr(self):
        position = Position(lat=1.0, lon=-1.1, accuracy=100.0, score=2.0)
        rep = repr(position)
        self.assertTrue(rep.startswith('Position'), rep)
        self.assertTrue('1.0' in rep, rep)
        self.assertTrue('-1.1' in rep, rep)
        self.assertTrue('100.0' in rep, rep)
        self.assertAlmostEqual(position.score, 2.0, 4)

    def test_data_accuracy(self):
        def _position(accuracy=None):
            return Position(lat=1.0, lon=1.0, accuracy=accuracy)

        self.assertEqual(
            _position().data_accuracy, DataAccuracy.none)
        self.assertEqual(
            _position(accuracy=0.0).data_accuracy, DataAccuracy.high)
        self.assertEqual(
            _position(accuracy=100).data_accuracy, DataAccuracy.high)
        self.assertEqual(
            _position(accuracy=20000.0).data_accuracy, DataAccuracy.medium)
        self.assertEqual(
            _position(accuracy=10 ** 6).data_accuracy, DataAccuracy.low)


class TestRegion(TestCase):

    def test_repr(self):
        region = Region(region_code='DE', region_name='Germany',
                        accuracy=100.0, score=2.0)
        rep = repr(region)
        self.assertTrue(rep.startswith('Region'), rep)
        self.assertTrue('DE' in rep, rep)
        self.assertTrue('Germany' in rep, rep)
        self.assertAlmostEqual(region.score, 2.0, 4)

    def test_data_accuracy(self):
        self.assertEqual(Region().data_accuracy, DataAccuracy.none)
        region = Region(
            region_code='DE', region_name='Germany', accuracy=100000.0)
        self.assertEqual(region.data_accuracy, DataAccuracy.low)
        region = Region(
            region_code='VA', region_name='Holy See', accuracy=1000.0)
        self.assertEqual(region.data_accuracy, DataAccuracy.high)


class TestResultList(TestCase):

    def _make_result(self):
        return Position(lat=1.0, lon=1.0, accuracy=10.0, score=0.5)

    def test_init(self):
        results = ResultList(self._make_result())
        self.assertEqual(len(results), 1)

    def test_repr(self):
        results = ResultList([self._make_result(), self._make_result()])
        rep = repr(results)
        self.assertTrue(rep.startswith('ResultList:'), rep)
        self.assertTrue('Position<' in rep, rep)
        self.assertTrue('lat:1.0' in rep, rep)
        self.assertTrue('lon:1.0' in rep, rep)
        self.assertTrue('accuracy:10.0' in rep, rep)
        self.assertTrue('score:0.5' in rep, rep)

    def test_add(self):
        results = ResultList()
        results.add(self._make_result())
        self.assertEqual(len(results), 1)

    def test_add_many(self):
        results = ResultList(self._make_result())
        results.add((self._make_result(), self._make_result()))
        self.assertEqual(len(results), 3)

    def test_len(self):
        results = ResultList()
        results.add(self._make_result())
        results.add(self._make_result())
        self.assertEqual(len(results), 2)

    def test_getitem(self):
        result = self._make_result()
        results = ResultList()
        results.add(result)
        self.assertEqual(results[0], result)

    def test_iterable(self):
        result = self._make_result()
        results = ResultList()
        results.add(result)
        results.add(result)
        for res in results:
            self.assertEqual(res, result)


class TestPositionResultList(TestCase):

    def test_repr(self):
        results = PositionResultList()
        self.assertTrue(repr(results).startswith('PositionResultList:'))

    def test_best_empty(self):
        self.assertTrue(PositionResultList().best() is None)

    def test_best(self):
        gb1 = Position(lat=51.5, lon=-0.1, accuracy=100000.0, score=0.6)
        gb2 = Position(lat=51.5002, lon=-0.1, accuracy=10000.0, score=1.5)
        gb3 = Position(lat=51.7, lon=-0.1, accuracy=1000.0, score=5.0)
        bt1 = Position(lat=27.5002, lon=90.5, accuracy=1000.0, score=0.5)
        bt2 = Position(lat=27.5, lon=90.5, accuracy=2000.0, score=2.0)
        bt3 = Position(lat=27.7, lon=90.7, accuracy=500.0, score=5.0)
        bt4 = Position(lat=27.9, lon=90.7, accuracy=300.0, score=5.0)

        # single result works
        self.assertAlmostEqual(PositionResultList(
            [gb1]).best().lat, 51.5, 4)

        # the lowest accuracy result from the best cluster wins
        self.assertAlmostEqual(PositionResultList(
            [bt1, bt2]).best().lat, 27.5002, 4)
        self.assertAlmostEqual(PositionResultList(
            [gb1, bt2]).best().lat, 27.5, 4)
        self.assertAlmostEqual(PositionResultList(
            [gb1, gb2, bt2]).best().lat, 51.5002, 4)
        self.assertAlmostEqual(PositionResultList(
            [gb1, gb3, bt1, bt2]).best().lat, 51.7, 4)
        self.assertAlmostEqual(PositionResultList(
            [gb1, gb2, bt2, bt3]).best().lat, 27.7, 4)

        # break tie by accuracy
        self.assertAlmostEqual(PositionResultList(
            [gb3, bt3]).best().lat, 27.7, 4)
        self.assertAlmostEqual(PositionResultList(
            [bt3, bt4]).best().lat, 27.9, 4)

    def test_satisfies(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi_query = [{'mac': wifi.mac} for wifi in wifis]
        positions = PositionResultList([
            Position(lat=1.0, lon=1.0, accuracy=100.0, score=0.5),
            Position(lat=1.0, lon=1.0, accuracy=10000.0, score=0.6)])
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertTrue(positions.satisfies(query))

    def test_satisfies_empty(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi_query = [{'mac': wifi.mac} for wifi in wifis]
        positions = PositionResultList()
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertFalse(positions.satisfies(query))

    def test_satisfies_fail(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi_query = [{'mac': wifi.mac} for wifi in wifis]
        positions = PositionResultList(
            Position(lat=1.0, lon=1.0, accuracy=2500.0, score=2.0))
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertFalse(positions.satisfies(query))


class TestRegionResultList(TestCase):

    def test_repr(self):
        results = RegionResultList()
        self.assertTrue(repr(results).startswith('RegionResultList:'))

    def test_best_empty(self):
        self.assertTrue(RegionResultList().best() is None)

    def test_best(self):
        us1 = Region(region_code='US', region_name='us',
                     accuracy=200000.0, score=3.0)
        us2 = Region(region_code='US', region_name='us',
                     accuracy=200000.0, score=3.0)
        gb1 = Region(region_code='GB', region_name='gb',
                     accuracy=100000.0, score=5.0)
        gb2 = Region(region_code='GB', region_name='gb',
                     accuracy=100000.0, score=3.0)

        # highest combined score wins
        self.assertEqual(RegionResultList(
            [us1, gb1]).best().region_code, 'GB')
        self.assertEqual(RegionResultList(
            [us1, gb1, us2]).best().region_code, 'US')

        # break tie by accuracy
        self.assertEqual(RegionResultList(
            [us1, gb2]).best().region_code, 'US')

    def test_satisfies(self):
        regions = RegionResultList(Region(
            region_code='DE', region_name='Germany', accuracy=100000.0))
        self.assertTrue(regions.satisfies(Query()))

    def test_satisfies_fail(self):
        regions = RegionResultList()
        self.assertFalse(regions.satisfies(Query()))
