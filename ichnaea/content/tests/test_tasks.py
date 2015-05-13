from datetime import timedelta

from ichnaea.models.content import (
    Stat,
    StatKey,
)
from ichnaea.content.tasks import unique_ocid_cell_histogram
from ichnaea.models import Radio
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import OCIDCellFactory
from ichnaea import util


class TestStats(CeleryTestCase):

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
