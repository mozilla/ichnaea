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

    def test_empty(self):
        self.assertTrue(Result().empty())


class TestPosition(TestCase):

    def test_repr(self):
        position = Position(lat=1.0, lon=-1.1, accuracy=100.0, score=2.0)
        rep = repr(position)
        self.assertTrue(rep.startswith('Position'), rep)
        self.assertTrue('1.0' in rep, rep)
        self.assertTrue('-1.1' in rep, rep)
        self.assertTrue('100.0' in rep, rep)
        self.assertAlmostEqual(position.score, 2.0, 4)

    def test_empty(self):
        self.assertTrue(Position(lat=1.0, lon=1.0, accuracy=None).empty())
        self.assertTrue(Position(lat=1.0, lon=None, accuracy=1.0).empty())
        self.assertTrue(Position(lat=None, lon=1.0, accuracy=1.0).empty())

    def test_not_empty(self):
        self.assertFalse(Position(lat=1.0, lon=1.0, accuracy=1.0).empty())
        self.assertFalse(Position(lat=0.0, lon=0.0, accuracy=0.0).empty())

    def test_as_list(self):
        self.assertEqual(type(Position().as_list()), PositionResultList)
        self.assertTrue(Position().as_list().best().empty())

    def test_new_list(self):
        self.assertEqual(type(Position().new_list()), PositionResultList)
        self.assertTrue(Position().new_list().best().empty())

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
        region = Region(region_code='DE', region_name='Germany', score=2.0)
        rep = repr(region)
        self.assertTrue(rep.startswith('Region'), rep)
        self.assertTrue('DE' in rep, rep)
        self.assertTrue('Germany' in rep, rep)
        self.assertAlmostEqual(region.score, 2.0, 4)

    def test_empty(self):
        region = Region(
            region_code='DE', region_name='Germany', accuracy=None)
        self.assertTrue(region.empty())
        region = Region(
            region_code='DE', region_name=None, accuracy=100000.0)
        self.assertTrue(region.empty())
        region = Region(
            region_code=None, region_name='Germany', accuracy=100000.0)
        self.assertTrue(region.empty())

    def test_not_empty(self):
        region = Region(
            region_code='DE', region_name='Germany', accuracy=100000.0)
        self.assertFalse(region.empty())

    def test_as_list(self):
        self.assertEqual(type(Region().as_list()), RegionResultList)
        self.assertTrue(Region().as_list().best().empty())

    def test_new_list(self):
        self.assertEqual(type(Region().new_list()), RegionResultList)
        self.assertTrue(Region().new_list().best().empty())

    def test_data_accuracy(self):
        self.assertEqual(Region().data_accuracy, DataAccuracy.none)
        region = Region(
            region_code='DE', region_name='Germany', accuracy=100000.0)
        self.assertEqual(region.data_accuracy, DataAccuracy.low)
        region = Region(
            region_code='VA', region_name='Holy See', accuracy=1000.0)
        self.assertEqual(region.data_accuracy, DataAccuracy.high)


class TestResultList(TestCase):

    def test_init(self):
        results = ResultList(Result())
        self.assertEqual(len(results), 1)

    def test_repr(self):
        results = ResultList([Position(lat=1.0), Position(lat=2.0)])
        rep = repr(results)
        self.assertTrue(rep.startswith('ResultList'), rep)
        self.assertTrue('Position<' in rep, rep)
        self.assertTrue('lat:1.0' in rep, rep)
        self.assertTrue('lat:2.0' in rep, rep)

    def test_add(self):
        results = ResultList()
        results.add(Result())
        self.assertEqual(len(results), 1)

    def test_add_many(self):
        results = ResultList(Result())
        results.add((Result(), Result()))
        self.assertEqual(len(results), 3)

    def test_len(self):
        results = ResultList()
        results.add(Result())
        results.add(Result())
        self.assertEqual(len(results), 2)

    def test_getitem(self):
        result = Result()
        results = ResultList()
        results.add(result)
        self.assertEqual(results[0], result)

    def test_iterable(self):
        result = Result()
        results = ResultList()
        results.add(result)
        results.add(result)
        for res in results:
            self.assertEqual(res, result)


class TestPositionResultList(TestCase):

    def test_best_empty(self):
        best_result = PositionResultList().best()
        self.assertTrue(best_result.empty())
        self.assertEqual(type(best_result), Position)

        results = PositionResultList([Position(), Position()])
        self.assertTrue(results.best().empty())

        # empty results are ignored
        results = PositionResultList([
            Position(),
            Position(lat=51.5, lon=-0.1, accuracy=100000.0, score=0.6),
            Position(),
        ])
        self.assertAlmostEqual(results.best().lat, 51.5, 4)

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

    def test_satisfies_fail(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi_query = [{'mac': wifi.mac} for wifi in wifis]
        positions = PositionResultList(
            Position(lat=1.0, lon=1.0, accuracy=2500.0, score=2.0))
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertFalse(positions.satisfies(query))


class TestRegionResultList(TestCase):

    def test_best_empty(self):
        best_result = RegionResultList().best()
        self.assertTrue(best_result.empty())
        self.assertEqual(type(best_result), Region)

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
        regions = RegionResultList(Region())
        self.assertFalse(regions.satisfies(Query()))
