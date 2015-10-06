from ichnaea.api.locate.constants import DataAccuracy
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import (
    Position,
    Region,
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

    def test_empty(self):
        self.assertTrue(Result().empty())

    def test_satisfies(self):
        self.assertFalse(Result().satisfies(Query()))

    def test_data_accuracy(self):
        self.assertEqual(Result().data_accuracy, DataAccuracy.none)


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


class TestRegion(TestCase):

    def test_repr(self):
        region = Region(region_code='DE', region_name='Germany')
        rep = repr(region)
        self.assertTrue(rep.startswith('Region'), rep)
        self.assertTrue('DE' in rep, rep)
        self.assertTrue('Germany' in rep, rep)

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

    def test_satisfies(self):
        region = Region(
            region_code='DE', region_name='Germany', accuracy=100000.0)
        self.assertTrue(region.satisfies(Query()))

    def test_satisfies_fail(self):
        region = Region()
        self.assertFalse(region.satisfies(Query()))

    def test_data_accuracy(self):
        self.assertEqual(Region().data_accuracy, DataAccuracy.none)
        region = Region(
            region_code='DE', region_name='Germany', accuracy=100000.0)
        self.assertEqual(region.data_accuracy, DataAccuracy.low)
        region = Region(
            region_code='VA', region_name='Holy See', accuracy=1000.0)
        self.assertEqual(region.data_accuracy, DataAccuracy.high)


class TestPosition(TestCase):

    def test_repr(self):
        position = Position(lat=1.0, lon=-1.1, accuracy=100.0)
        rep = repr(position)
        self.assertTrue(rep.startswith('Position'), rep)
        self.assertTrue('1.0' in rep, rep)
        self.assertTrue('-1.1' in rep, rep)
        self.assertTrue('100.0' in rep, rep)

    def test_empty(self):
        self.assertTrue(Position(lat=1.0, lon=1.0, accuracy=None).empty())
        self.assertTrue(Position(lat=1.0, lon=None, accuracy=1.0).empty())
        self.assertTrue(Position(lat=None, lon=1.0, accuracy=1.0).empty())

    def test_not_empty(self):
        self.assertFalse(Position(lat=1.0, lon=1.0, accuracy=1.0).empty())
        self.assertFalse(Position(lat=0.0, lon=0.0, accuracy=0.0).empty())

    def test_satisfies(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi_query = [{'mac': wifi.mac} for wifi in wifis]
        position = Position(lat=1.0, lon=1.0, accuracy=100.0)
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertTrue(position.satisfies(query))

    def test_satisfies_fail(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi_query = [{'mac': wifi.mac} for wifi in wifis]
        position = Position(lat=1.0, lon=1.0, accuracy=2500.0)
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertFalse(position.satisfies(query))

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
            _position(accuracy=30000.0).data_accuracy, DataAccuracy.medium)
        self.assertEqual(
            _position(accuracy=10 ** 6).data_accuracy, DataAccuracy.low)
