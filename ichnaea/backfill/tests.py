from sqlalchemy import text

from ichnaea.backfill.tasks import do_backfill
from ichnaea.models import (
    Cell,
    CellMeasure,
)
from ichnaea.tests.base import CeleryTestCase


class TestBackfill(CeleryTestCase):

    def test_do_backfill(self):
        session = self.db_master_session

        # These are our reference towers that will be used to match
        # similar towers
        data = [
            # These are measurements for tower A
            Cell(lat=37.83486, lon=-12.2282873, radio=2,
                 lac=56955, cid=5286246, mcc=310, mnc=410, psc=38,
                 new_measures=0, total_measures=1),

            # These are measurements for tower B
            Cell(lat=30, lon=-20, radio=3,
                 lac=20, cid=31, mcc=310, mnc=410, psc=38,
                 new_measures=0, total_measures=1),
        ]
        session.add_all(data)

        # This is tower C and should map back to tower A
        towerC_lat = 37.8348600
        towerC_lon = -12.22828703
        session.add_all([CellMeasure(lat=towerC_lat, lon=towerC_lon, radio=2,
                                     lac=-1, cid=-1, mcc=310, mnc=410, psc=38,
                                     accuracy=20)])

        # This is tower D and should map back to tower B
        session.add_all([CellMeasure(lat=30, lon=-20, radio=3,
                                     lac=-1, cid=-1, mcc=310, mnc=410, psc=38,
                                     accuracy=20)])

        # This is tower E and should not map back to anything as the
        # radio doesn't match up
        session.add_all([CellMeasure(lat=30, lon=-20, radio=0,
                                     lac=-1, cid=-1, mcc=310, mnc=410, psc=38,
                                     accuracy=20)])

        # This is tower F and should not map back to anything as it's
        # too far away.
        session.add_all([CellMeasure(lat=9.8409925, lon=9.8409925, radio=3,
                                     lac=-1, cid=-1, mcc=310, mnc=410, psc=38,
                                     accuracy=20)])

        session.commit()
        do_backfill.delay()

        # check that tower C was mapped correctly
        rset = session.execute(text(
            "select * from cell_measure where "
            "radio = 2 and lac = 56955 and cid = 5286246"))
        rset = list(rset)
        self.assertEquals(len(rset), 1)
        lat_longs = [(row['lat'], row['lon']) for row in rset]
        assert (towerC_lat, towerC_lon) in lat_longs

        # check that tower D was mapped correctly
        rset = session.execute(text(
            "select * from cell_measure where "
            "radio = 3 and lac = 20 and cid = 31"))
        rset = list(rset)
        self.assertEquals(len(rset), 1)
        lat_longs = [(row['lat'], row['lon']) for row in rset]
        assert (30, -20) in lat_longs

        # we shouldn't map tower E when the known towers have
        # different radios than our incomplete tower records
        rset = session.execute(text(
            "select count(*) from cell_measure where "
            "radio = 0 and lac = - 1 and cid = -1"))
        rset = list(rset)
        self.assertEquals(len(rset), 1)

        # Tower F shouldn't map to any known tower as it's too far away
        rset = session.execute(text(
            "select count(*) from cell_measure where radio = 3 and "
            "lat = 9.8409925 and lon = 9.8409925 and lac = -1 and cid = -1"))
        rset = list(rset)
        self.assertEquals(len(rset), 1)
