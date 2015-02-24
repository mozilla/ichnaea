from datetime import timedelta

from ichnaea.models.content import (
    Stat,
    StatKey,
)
from ichnaea.content.tasks import (
    cell_histogram,
    unique_cell_histogram,
    unique_ocid_cell_histogram,
    unique_wifi_histogram,
    wifi_histogram,
)
from ichnaea.models import Radio
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellFactory,
    CellObservationFactory,
    OCIDCellFactory,
    WifiFactory,
    WifiObservationFactory,
)
from ichnaea import util


class TestStats(CeleryTestCase):

    def test_cell_histogram(self):
        session = self.session
        today = util.utcnow()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))

        for i in range(2):
            CellObservationFactory(created=today)
        CellObservationFactory(created=yesterday)
        for i in range(3):
            CellObservationFactory(created=two_days)
        CellObservationFactory(created=long_ago)
        session.flush()

        cell_histogram.delay(ago=3).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, StatKey.cell)
        self.assertEqual(stats[0].time, long_ago.date())
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        cell_histogram.delay(ago=2).get()
        cell_histogram.delay(ago=1).get()
        cell_histogram.delay(ago=0).get()

        # test duplicate execution
        cell_histogram.delay(ago=1).get()

        stats = session.query(Stat.time, Stat.value).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(dict(stats), {
                         long_ago.date(): 1,
                         two_days.date(): 4,
                         yesterday.date(): 5,
                         today.date(): 7})

    def test_unique_cell_histogram(self):
        session = self.session
        today = util.utcnow()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))

        CellFactory(created=long_ago, radio=Radio.gsm)
        CellFactory(created=two_days, radio=Radio.umts)
        CellFactory(created=two_days, radio=Radio.umts, cid=50)
        CellFactory(created=yesterday, radio=Radio.lte, cid=50)
        CellFactory(created=today, radio=Radio.gsm, mnc=30)
        session.flush()

        result = unique_cell_histogram.delay(ago=3)
        self.assertEqual(result.get(), 1)

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, StatKey.unique_cell)
        self.assertEqual(stats[0].time, long_ago.date())
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        unique_cell_histogram.delay(ago=2).get()
        unique_cell_histogram.delay(ago=1).get()
        unique_cell_histogram.delay(ago=0).get()

        # test duplicate execution
        unique_cell_histogram.delay(ago=1).get()

        stats = session.query(Stat.time, Stat.value).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(dict(stats), {
                         long_ago.date(): 1,
                         two_days.date(): 3,
                         yesterday.date(): 4,
                         today.date(): 5})

    def test_unique_ocid_cell_histogram(self):
        session = self.session
        today = util.utcnow()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))

        OCIDCellFactory(created=long_ago)
        OCIDCellFactory(created=two_days, radio=Radio.umts)
        OCIDCellFactory(created=two_days, radio=Radio.umts, cid=50)
        OCIDCellFactory(created=yesterday, radio=Radio.lte, cid=50)
        OCIDCellFactory(created=today, mnc=30)
        OCIDCellFactory(created=today, lac=40)
        session.flush()

        result = unique_ocid_cell_histogram.delay(ago=3)
        self.assertEqual(result.get(), 1)

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, StatKey.unique_ocid_cell)
        self.assertEqual(stats[0].time, long_ago.date())
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        unique_ocid_cell_histogram.delay(ago=2).get()
        unique_ocid_cell_histogram.delay(ago=1).get()
        unique_ocid_cell_histogram.delay(ago=0).get()

        # test duplicate execution
        unique_ocid_cell_histogram.delay(ago=1).get()

        stats = session.query(Stat.time, Stat.value).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(dict(stats), {
                         long_ago.date(): 1,
                         two_days.date(): 3,
                         yesterday.date(): 4,
                         today.date(): 6})

    def test_wifi_histogram(self):
        session = self.session
        today = util.utcnow()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))

        for i in range(2):
            WifiObservationFactory(created=today)
        WifiObservationFactory(created=yesterday)
        for i in range(3):
            WifiObservationFactory(created=two_days)
        WifiObservationFactory(created=long_ago)
        session.flush()

        wifi_histogram.delay(ago=3).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, StatKey.wifi)
        self.assertEqual(stats[0].time, long_ago.date())
        self.assertEqual(stats[0].value, 1)

        # fill in newer dates
        wifi_histogram.delay(ago=2).get()
        wifi_histogram.delay(ago=1).get()
        wifi_histogram.delay(ago=0).get()

        # test duplicate execution
        wifi_histogram.delay(ago=1).get()

        stats = session.query(Stat.time, Stat.value).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(dict(stats), {
                         long_ago.date(): 1,
                         two_days.date(): 4,
                         yesterday.date(): 5,
                         today.date(): 7})

    def test_unique_wifi_histogram(self):
        session = self.session
        today = util.utcnow()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))

        WifiFactory(key="ab1234567890", created=long_ago)
        WifiFactory(key="bc1234567890", created=two_days)
        WifiFactory(key="cd1234567890", created=yesterday)
        WifiFactory(key="de1234567890", created=yesterday)
        WifiFactory(key="ef1234567890", created=today)
        session.flush()

        result = unique_wifi_histogram.delay(ago=3)
        added = result.get()
        self.assertEqual(added, 1)

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, StatKey.unique_wifi)
        self.assertEqual(stats[0].time, long_ago.date())
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        unique_wifi_histogram.delay(ago=2).get()
        unique_wifi_histogram.delay(ago=1).get()
        unique_wifi_histogram.delay(ago=0).get()

        # test duplicate execution
        unique_wifi_histogram.delay(ago=1).get()

        stats = session.query(Stat.time, Stat.value).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(dict(stats), {
                         long_ago.date(): 1,
                         two_days.date(): 2,
                         yesterday.date(): 4,
                         today.date(): 5})
