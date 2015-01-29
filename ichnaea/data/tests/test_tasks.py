import base64
from datetime import timedelta
import json
import zlib

from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text

from ichnaea.constants import (
    PERMANENT_BLACKLIST_THRESHOLD,
    TEMPORARY_BLACKLIST_DURATION,
)
from ichnaea.content.models import (
    Score,
    SCORE_TYPE,
)
from ichnaea.customjson import encode_datetime
from ichnaea.data import constants
from ichnaea.data.schema import ValidCellBaseSchema
from ichnaea.data.tasks import (
    UPDATE_KEY,
    enqueue_lacs,
    location_update_cell,
    location_update_wifi,
    insert_measures_cell,
    insert_measures_wifi,
    remove_cell,
    remove_wifi,
    scan_lacs,
)
from ichnaea.logging import RAVEN_ERROR
from ichnaea.models import (
    Cell,
    CellArea,
    CellAreaKey,
    CellBlacklist,
    CellKey,
    CellMeasure,
    RADIO_TYPE,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
    to_cellkey,
)
from ichnaea.tests.base import (
    CeleryTestCase,
    PARIS_LAT, PARIS_LON, FRANCE_MCC,
    USA_MCC, ATT_MNC,
)
from ichnaea import util


class TestCell(CeleryTestCase):

    def add_line_of_cells_and_scan_lac(self):
        session = self.db_master_session
        big = 1.0
        small = big / 10
        keys = dict(radio=1, mcc=1, mnc=1, lac=1)
        measures = [
            CellMeasure(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(10)
            for ctr in [cell * big]
            for (xd, yd) in [(small, small),
                             (small, -small),
                             (-small, small),
                             (-small, -small)]
        ]
        session.add_all(measures)

        cells = [
            Cell(lat=ctr, lon=ctr, cid=cell,
                 new_measures=4, total_measures=1, **keys)
            for cell in range(10)
            for ctr in [cell * big]
        ]

        session.add_all(cells)
        session.commit()
        result = location_update_cell.delay(min_new=0,
                                            max_new=9999,
                                            batch=len(measures))
        self.assertEqual(result.get(), (len(cells), 0))
        scan_lacs.delay()

    def test_blacklist(self):
        session = self.db_master_session

        measures = [dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=i, psc=5,
                         radio=RADIO_TYPE['gsm'],
                         lat=PARIS_LAT + i * 0.0000001,
                         lon=PARIS_LON + i * 0.0000001) for i in range(1, 4)]

        black = CellBlacklist(
            mcc=FRANCE_MCC, mnc=2, lac=3, cid=1,
            radio=RADIO_TYPE['gsm'],
        )
        session.add(black)
        session.flush()

        result = insert_measures_cell.delay(measures)
        self.assertEqual(result.get(), 2)

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 2)

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 2)

    def test_blacklist_moving_cells(self):
        now = util.utcnow()
        long_ago = now - timedelta(days=40)
        session = self.db_master_session

        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        k2 = dict(radio=1, mcc=1, mnc=2, lac=6, cid=8)
        k3 = dict(radio=1, mcc=1, mnc=2, lac=9, cid=12)
        k4 = dict(radio=1, mcc=1, mnc=2, lac=12, cid=16)
        k5 = dict(radio=1, mcc=1, mnc=2, lac=15, cid=20)
        k6 = dict(radio=1, mcc=1, mnc=2, lac=18, cid=24)

        keys = set([CellKey(**k) for k in [k1, k2, k3, k4, k5, k6]])

        # keys k2, k3 and k4 are expected to be detected as moving
        data = [
            # a cell with an entry but no prior position
            Cell(new_measures=3, total_measures=0, **k1),
            CellMeasure(lat=1.001, lon=1.001, **k1),
            CellMeasure(lat=1.002, lon=1.005, **k1),
            CellMeasure(lat=1.003, lon=1.009, **k1),
            # a cell with a prior known position
            Cell(lat=2.0, lon=2.0,
                 new_measures=2, total_measures=1, **k2),
            CellMeasure(lat=2.0, lon=2.0, **k2),
            CellMeasure(lat=4.0, lon=2.0, **k2),
            # a cell with a very different prior position
            Cell(lat=1.0, lon=1.0,
                 new_measures=2, total_measures=1, **k3),
            CellMeasure(lat=3.0, lon=3.0, **k3),
            CellMeasure(lat=-3.0, lon=3.0, **k3),
            # another cell with a prior known position (and negative lat)
            Cell(lat=-4.0, lon=4.0,
                 new_measures=2, total_measures=1, **k4),
            CellMeasure(lat=-4.0, lon=4.0, **k4),
            CellMeasure(lat=-6.0, lon=4.0, **k4),
            # an already blacklisted cell
            CellBlacklist(**k5),
            CellMeasure(lat=5.0, lon=5.0, **k5),
            CellMeasure(lat=8.0, lon=5.0, **k5),
            # a cell with an old different record we ignore, position
            # estimate has been updated since
            Cell(lat=6.0, lon=6.0,
                 new_measures=2, total_measures=1, **k6),
            CellMeasure(lat=6.9, lon=6.9, time=long_ago, **k6),
            CellMeasure(lat=6.0, lon=6.0, **k6),
            CellMeasure(lat=6.001, lon=6, **k6),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        black = session.query(CellBlacklist).all()
        self.assertEqual(set([to_cellkey(b) for b in black]),
                         set([CellKey(**k) for k in [k2, k3, k4, k5]]))

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 14)
        self.assertEqual(set([to_cellkey(m) for m in measures]), keys)

        # test duplicate call
        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), 0)

        self.check_stats(
            total=6,
            timer=[
                # We made duplicate calls
                ('task.data.location_update_cell', 2),
                # One of those would've scheduled a remove_cell task
                ('task.data.remove_cell', 1)
            ],
            gauge=[
                ('task.data.location_update_cell.new_measures_1_100', 2),
            ])

    def test_blacklist_temporary_and_permanent(self):
        session = self.db_master_session

        # This test simulates a cell that moves once a month, for 2 years.
        # The first 2 * PERMANENT_BLACKLIST_THRESHOLD (12) moves should be
        # temporary, forgotten after a week; after that it should be
        # permanently blacklisted.

        now = util.utcnow()
        # Station moves between these 4 points, all in the USA:
        points = [
            # NYC
            (40.0, -74.0),
            # SF
            (37.0, -122.0),
            # Seattle
            (47.0, -122.0),
            # Miami
            (25.0, -80.0),
        ]

        N = 4 * PERMANENT_BLACKLIST_THRESHOLD
        for month in range(0, N):
            days_ago = (N - (month + 1)) * 30
            time = now - timedelta(days=days_ago)
            time_enc = encode_datetime(time)

            measure = dict(radio=RADIO_TYPE['gsm'],
                           mcc=USA_MCC, mnc=ATT_MNC, lac=456, cid=123,
                           time=time_enc,
                           lat=points[month % 4][0],
                           lon=points[month % 4][1])

            # insert_result is num-accepted-measures, override
            # utcnow to set creation date
            insert_result = insert_measures_cell.delay(
                [measure], utcnow=time_enc)

            # update_result is (num-stations, num-moving-stations)
            update_result = location_update_cell.delay(min_new=1)

            # Assuming PERMANENT_BLACKLIST_THRESHOLD == 6:
            #
            # 0th insert will create the station
            # 1st insert will create first blacklist entry, delete station
            # 2nd insert will recreate the station at new position
            # 3rd insert will update blacklist, re-delete station
            # 4th insert will recreate the station at new position
            # 5th insert will update blacklist, re-delete station
            # 6th insert will recreate the station at new position
            # ...
            # 11th insert will make blacklisting permanent, re-delete station
            # 12th insert will not recreate station
            # 13th insert will not recreate station
            # ...
            # 23rd insert will not recreate station

            bl = session.query(CellBlacklist).all()
            if month == 0:
                self.assertEqual(len(bl), 0)
            else:
                self.assertEqual(len(bl), 1)
                # force the blacklist back in time to whenever the
                # measure was supposedly inserted.
                bl = bl[0]
                bl.time = time
                session.add(bl)
                session.commit()

            if month < N / 2:
                # We still haven't exceeded the threshold, so the
                # measurement was admitted.
                self.assertEqual(insert_result.get(), 1)
                self.assertEqual(session.query(CellMeasure).count(), month + 1)
                if month % 2 == 0:
                    # The station was (re)created.
                    self.assertEqual(update_result.get(), (1, 0))
                    # Rescan lacs to update entries
                    self.assertEqual(
                        scan_lacs.delay().get(), 1)
                    # One cell + one cell-LAC record should exist.
                    self.assertEqual(session.query(Cell).count(), 1)
                    self.assertEqual(session.query(CellArea).count(), 1)
                else:
                    # The station existed and was seen moving,
                    # thereby activating the blacklist and deleting the cell.
                    self.assertEqual(update_result.get(), (1, 1))
                    # Rescan lacs to delete orphaned lac entry
                    self.assertEqual(
                        scan_lacs.delay().get(), 1)
                    self.assertEqual(bl.count, ((month + 1) / 2))
                    self.assertEqual(session.query(CellBlacklist).count(), 1)
                    self.assertEqual(session.query(Cell).count(), 0)

                    # Try adding one more measurement 1 day later
                    # to be sure it is dropped by the now-active blacklist.
                    next_day = encode_datetime(time + timedelta(days=1))
                    measure['time'] = next_day
                    self.assertEqual(
                        0, insert_measures_cell.delay([measure],
                                                      utcnow=next_day).get())

            else:
                # Blacklist has exceeded threshold, gone to "permanent" mode,
                # so no measures accepted, no stations seen.
                self.assertEqual(insert_result.get(), 0)
                self.assertEqual(update_result.get(), 0)

    def test_blacklist_time_used_as_creation_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLACKLIST_DURATION - timedelta(days=1)
        session = self.db_master_session

        cell_key = {'radio': RADIO_TYPE['gsm'], 'mcc': FRANCE_MCC,
                    'mnc': 2, 'lac': 3, 'cid': 1}

        session.add(CellBlacklist(time=last_week, **cell_key))
        session.flush()

        # add a new entry for the previously blacklisted cell
        measure = dict(lat=PARIS_LAT, lon=PARIS_LON, **cell_key)
        insert_measures_cell.delay([measure]).get()

        # the cell was inserted again
        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)

        # and the creation date was set to the date of the blacklist entry
        self.assertEqual(cells[0].created, last_week)

    def test_insert_measures(self):
        session = self.db_master_session
        time = util.utcnow() - timedelta(days=1)
        mcc = FRANCE_MCC

        session.add(Cell(radio=RADIO_TYPE['gsm'], mcc=mcc, mnc=2, lac=3,
                         cid=4, psc=5, new_measures=2,
                         total_measures=5))
        session.add(Score(userid=1, key=SCORE_TYPE['new_cell'], value=7))
        session.flush()

        measure = dict(
            created=encode_datetime(time),
            lat=PARIS_LAT,
            lon=PARIS_LON,
            time=encode_datetime(time), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=RADIO_TYPE['gsm'],
        )
        entries = [
            # Note that this first entry will be skipped as it does
            # not include (lac, cid) or (psc)
            {"mcc": mcc, "mnc": 2, "signal": -100},

            {"mcc": mcc, "mnc": 2, "lac": 3, "cid": 4, "psc": 5, "asu": 8},
            {"mcc": mcc, "mnc": 2, "lac": 3, "cid": 4, "psc": 5, "asu": 8},
            {"mcc": mcc, "mnc": 2, "lac": 3, "cid": 4, "psc": 5, "asu": 15},
            {"mcc": mcc, "mnc": 2, "lac": 3, "cid": 7, "psc": 5},
        ]
        for e in entries:
            e.update(measure)

        result = insert_measures_cell.delay(entries, userid=1)

        self.assertEqual(result.get(), 4)
        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 4)
        self.assertEqual(set([m.mcc for m in measures]), set([mcc]))
        self.assertEqual(set([m.mnc for m in measures]), set([2]))
        self.assertEqual(set([m.asu for m in measures]), set([-1, 8, 15]))
        self.assertEqual(set([m.psc for m in measures]), set([5]))
        self.assertEqual(set([m.signal for m in measures]), set([0]))

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 2)
        self.assertEqual(set([c.mcc for c in cells]), set([mcc]))
        self.assertEqual(set([c.mnc for c in cells]), set([2]))
        self.assertEqual(set([c.lac for c in cells]), set([3]))
        self.assertEqual(set([c.cid for c in cells]), set([4, 7]))
        self.assertEqual(set([c.psc for c in cells]), set([5]))
        self.assertEqual(set([c.new_measures for c in cells]), set([1, 5]))
        self.assertEqual(set([c.total_measures for c in cells]), set([1, 8]))

        scores = session.query(Score).all()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].key, SCORE_TYPE['new_cell'])
        self.assertEqual(scores[0].value, 8)

        # test duplicate execution
        result = insert_measures_cell.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)
        # TODO this task isn't idempotent yet
        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 8)

    def test_insert_measures_invalid_lac(self):
        session = self.db_master_session
        schema = ValidCellBaseSchema()
        time = util.utcnow() - timedelta(days=1)

        session.add(Cell(radio=RADIO_TYPE['gsm'], mcc=FRANCE_MCC, mnc=2,
                         lac=3, cid=4, new_measures=2, total_measures=5))
        session.add(Score(userid=1, key=SCORE_TYPE['new_cell'], value=7))
        session.flush()

        measure = dict(
            created=encode_datetime(time),
            lat=PARIS_LAT,
            lon=PARIS_LON,
            time=encode_datetime(time), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=RADIO_TYPE['gsm'])
        entries = [
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": constants.MAX_LAC_ALL + 1,
             "cid": constants.MAX_CID_ALL + 1, "psc": 5, "asu": 8},
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": schema.fields['lac'].missing,
             "cid": schema.fields['cid'].missing, "psc": 5, "asu": 8},
        ]
        for e in entries:
            e.update(measure)

        result = insert_measures_cell.delay(entries, userid=1)
        self.assertEqual(result.get(), 2)

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 2)
        self.assertEqual(
            set([m.lac for m in measures]),
            set([schema.fields['lac'].missing]))
        self.assertEqual(
            set([m.cid for m in measures]),
            set([schema.fields['cid'].missing]))

        # Nothing should change in the initially created Cell record
        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        self.assertEqual(set([c.new_measures for c in cells]), set([2]))
        self.assertEqual(set([c.total_measures for c in cells]), set([5]))

    def test_insert_measures_overflow(self):
        session = self.db_master_session

        measures = [dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4, psc=5,
                         radio=RADIO_TYPE['gsm'],
                         lat=PARIS_LAT + i * 0.0000001,
                         lon=PARIS_LON + i * 0.0000001) for i in range(3)]

        result = insert_measures_cell.delay(measures)
        self.assertEqual(result.get(), 3)

        result = insert_measures_cell.delay(measures, max_measures_per_cell=3)
        self.assertEqual(result.get(), 0)

        result = insert_measures_cell.delay(measures, max_measures_per_cell=10)
        self.assertEqual(result.get(), 3)

        result = insert_measures_cell.delay(measures, max_measures_per_cell=3)
        self.assertEqual(result.get(), 0)

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 6)

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0].total_measures, 6)

    def test_insert_measures_out_of_range(self):
        session = self.db_master_session
        time = util.utcnow() - timedelta(days=1)

        measure = dict(
            created=encode_datetime(time),
            lat=PARIS_LAT,
            lon=PARIS_LON,
            time=encode_datetime(time), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=RADIO_TYPE['gsm'], mcc=FRANCE_MCC,
            mnc=2, lac=3, cid=4)
        entries = [
            {"asu": 8, "signal": -70, "ta": 32},
            {"asu": -10, "signal": -300, "ta": -10},
            {"asu": 256, "signal": 16, "ta": 128},
        ]
        for e in entries:
            e.update(measure)

        result = insert_measures_cell.delay(entries)
        self.assertEqual(result.get(), 3)

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 3)
        self.assertEqual(set([m.asu for m in measures]), set([-1, 8]))
        self.assertEqual(set([m.signal for m in measures]), set([0, -70]))
        self.assertEqual(set([m.ta for m in measures]), set([0, 32]))

    def test_location_update_cell(self):
        now = util.utcnow()
        before = now - timedelta(days=1)
        schema = ValidCellBaseSchema()
        session = self.db_master_session

        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        k2 = dict(radio=1, mcc=1, mnc=2, lac=6, cid=8)
        k3 = dict(radio=1, mcc=1, mnc=2,
                  lac=schema.fields['lac'].missing,
                  cid=schema.fields['cid'].missing)
        data = [
            Cell(new_measures=3, total_measures=5, **k1),
            CellMeasure(lat=1.0, lon=1.0, **k1),
            CellMeasure(lat=1.002, lon=1.003, **k1),
            CellMeasure(lat=1.004, lon=1.006, **k1),
            # The lac, cid are invalid and should be skipped
            CellMeasure(lat=1.5, lon=1.5, **k3),
            CellMeasure(lat=1.502, lon=1.503, **k3),

            Cell(lat=2.0, lon=2.0,
                 new_measures=2, total_measures=4, **k2),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old measures are skipped
            CellMeasure(lat=-1.0, lon=-1.0, created=before, **k2),
            CellMeasure(lat=-1.0, lon=-1.0, created=before, **k2),
            CellMeasure(lat=2.002, lon=2.004, **k2),
            CellMeasure(lat=2.002, lon=2.004, **k2),

        ]
        session.add_all(data)
        session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (2, 0))
        self.check_stats(
            total=2,
            timer=['task.data.location_update_cell'],
            gauge=['task.data.location_update_cell.new_measures_1_100'],
        )

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 2)
        self.assertEqual([c.new_measures for c in cells], [0, 0])
        for cell in cells:
            if cell.cid == 4:
                self.assertEqual(cell.lat, 1.002)
                self.assertEqual(cell.lon, 1.003)
            elif cell.cid == 8:
                self.assertEqual(cell.lat, 2.001)
                self.assertEqual(cell.lon, 2.002)

    def test_max_min_range_update(self):
        session = self.db_master_session

        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        data = [
            Cell(lat=1.001, lon=-1.001,
                 max_lat=1.002, min_lat=1.0,
                 max_lon=-1.0, min_lon=-1.002,
                 new_measures=2, total_measures=4, **k1),
            CellMeasure(lat=1.001, lon=-1.003, **k1),
            CellMeasure(lat=1.005, lon=-1.007, **k1),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (1, 0))

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        self.assertEqual(cell.lat, 1.002)
        self.assertEqual(cell.max_lat, 1.005)
        self.assertEqual(cell.min_lat, 1.0)
        self.assertEqual(cell.lon, -1.003)
        self.assertEqual(cell.max_lon, -1.0)
        self.assertEqual(cell.min_lon, -1.007)

        # independent calculation: the cell bounding box is
        # (1.000, -1.007) to (1.005, -1.000), with centroid
        # at (1.002, -1.003); worst distance from centroid
        # to any corner is 556m
        self.assertEqual(cell.range, 556)

    def test_removal_updates_lac(self):
        session = self.db_master_session
        keys = dict(radio=1, mcc=1, mnc=1, lac=1)

        # setup: build LAC as above
        self.add_line_of_cells_and_scan_lac()

        # confirm we got one
        lac = session.query(CellArea).filter(CellArea.lac == 1).first()

        self.assertEqual(lac.lat, 4.5)
        self.assertEqual(lac.lon, 4.5)
        self.assertEqual(lac.range, 723001)

        # Remove cells one by one checking that the LAC
        # changes shape along the way.
        steps = [
            ((5.0, 5.0), 644242),
            ((5.5, 5.5), 565475),
            ((6.0, 6.0), 486721),
            ((6.5, 6.5), 408000),
            ((7.0, 7.0), 329334),
            ((7.5, 7.5), 250743),
            ((8.0, 8.0), 172249),
            ((8.5, 8.5), 93871),
            ((9.0, 9.0), 15630),
        ]
        for i in range(9):
            session.expire(lac)
            k = CellKey(cid=i, **keys)
            result = remove_cell.delay([k])
            self.assertEqual(1, result.get())
            result = scan_lacs.delay()
            self.assertEqual(1, result.get())
            lac = session.query(CellArea).filter(CellArea.lac == 1).first()

            self.assertEqual(lac.lat, steps[i][0][0])
            self.assertEqual(lac.lon, steps[i][0][1])
            self.assertEqual(lac.range, steps[i][1])

        # Remove final cell, check LAC is gone
        k = CellKey(cid=9, **keys)
        result = remove_cell.delay([k])
        self.assertEqual(1, result.get())
        result = scan_lacs.delay()
        self.assertEqual(1, result.get())
        lac = session.query(CellArea).filter(CellArea.lac == 1).first()
        self.assertEqual(lac, None)

    def test_scan_lacs_asymmetric(self):
        session = self.db_master_session
        big = 0.1
        small = big / 10
        keys = dict(radio=1, mcc=1, mnc=1, lac=1)
        measures = [
            CellMeasure(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(6)
            for ctr in [(2 ** cell) * big]
            for (xd, yd) in [(small, small),
                             (small, -small),
                             (-small, small),
                             (-small, -small)]
        ]
        session.add_all(measures)

        cells = [
            Cell(lat=ctr, lon=ctr, cid=cell,
                 new_measures=4, total_measures=1, **keys)
            for cell in range(6)
            for ctr in [(2 ** cell) * big]
        ]

        session.add_all(cells)
        session.commit()
        result = location_update_cell.delay(min_new=0,
                                            max_new=9999,
                                            batch=len(measures))
        self.assertEqual(result.get(), (len(cells), 0))
        scan_lacs.delay()
        lac = session.query(CellArea).filter(CellArea.lac == 1).first()

        # We produced a sequence of 0.02-degree-on-a-side
        # cell bounding boxes centered at
        # [0, 0.2, 0.4, 0.8, 1.6, 3.2] degrees.
        # So the lower-left corner is at (-0.01, -0.01)
        # and the upper-right corner is at (3.21, 3.21)
        # we should therefore see a LAC centroid at (1.05, 1.05)
        # with a range of 339.540m
        self.assertEqual(lac.lat, 1.05)
        self.assertEqual(lac.lon, 1.05)
        self.assertEqual(lac.range, 339540)

    def test_scan_lacs_race_with_location_update(self):
        session = self.db_master_session

        # First batch of cell measurements for CID 1
        keys = dict(radio=1, mcc=1, mnc=1, lac=1, cid=1)
        cell = Cell(new_measures=4, total_measures=1, **keys)
        measures = [
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
        ]
        session.add(cell)
        session.add_all(measures)
        session.commit()

        # Periodic location_update_cell runs and updates CID 1
        # to have a location, inserts LAC 1 with new_measures=1
        # which will be picked up by the next scan_lac.
        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (1, 0))

        # Second batch of cell measurements for CID 2
        keys['cid'] = 2
        cell = Cell(new_measures=4, total_measures=1, **keys)
        measures = [
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
        ]
        session.add(cell)
        session.add_all(measures)
        session.commit()

        # Periodic LAC scan runs, picking up LAC 1; this could
        # accidentally pick up CID 2, but it should not since it
        # has not had its location updated yet. If there's no
        # exception here, CID 2 is properly ignored.
        scan_lacs.delay()

    def test_scan_lacs_empty(self):
        # test tasks with an empty queue
        self.assertEqual(scan_lacs.delay().get(), 0)
        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 0)]
        )

    def test_scan_lacs_remove(self):
        session = self.db_master_session
        redis_client = self.redis_client

        # create an orphaned lac entry
        key = dict(radio=1, mcc=1, mnc=1, lac=1)
        session.add(CellArea(**key))
        session.flush()
        enqueue_lacs(session, redis_client,
                     [CellAreaKey(**key)], UPDATE_KEY['cell_lac'])

        # after scanning the orphaned record gets removed
        self.assertEqual(scan_lacs.delay().get(), 1)
        lacs = session.query(CellArea).all()
        self.assertEqual(lacs, [])

    def test_scan_lacs_update(self):
        session = self.db_master_session
        self.add_line_of_cells_and_scan_lac()
        today = util.utcnow().date()

        lac = session.query(CellArea).filter(Cell.lac == 1).first()

        # We produced a sequence of 0.2-degree-on-a-side
        # cell bounding boxes centered at [0, 1, 2, ..., 9]
        # degrees. So the lower-left corner is at (-0.1, -0.1)
        # and the upper-right corner is at (9.1, 9.1)
        # we should therefore see a LAC centroid at (4.5, 4.5)
        # with a range of 723,001m
        self.assertEqual(lac.lat, 4.5)
        self.assertEqual(lac.lon, 4.5)
        self.assertEqual(lac.range, 723001)
        self.assertEqual(lac.created.date(), today)
        self.assertEqual(lac.modified.date(), today)
        self.assertEqual(lac.num_cells, 10)


class TestWifi(CeleryTestCase):

    def test_blacklist(self):
        session = self.db_master_session
        bad_key = "ab1234567890"
        good_key = "cd1234567890"
        black = WifiBlacklist(key=bad_key)
        session.add(black)
        session.flush()
        measure = dict(lat=1, lon=2)
        entries = [{"key": good_key}, {"key": good_key}, {"key": bad_key}]
        for e in entries:
            e.update(measure)

        result = insert_measures_wifi.delay(entries)
        self.assertEqual(result.get(), 2)

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 2)
        self.assertEqual(
            set([m.key for m in measures]), set([good_key]))

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)
        self.assertEqual(set([w.key for w in wifis]), set([good_key]))

    def test_blacklist_moving_wifis(self):
        now = util.utcnow()
        long_ago = now - timedelta(days=40)
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "bc1234567890"
        k3 = "cd1234567890"
        k4 = "de1234567890"
        k5 = "ef1234567890"
        k6 = "fa1234567890"

        keys = set([k1, k2, k3, k4, k5, k6])

        # keys k2, k3 and k4 are expected to be detected as moving
        data = [
            # a wifi with an entry but no prior position
            Wifi(key=k1, new_measures=3, total_measures=0),
            WifiMeasure(lat=1.001, lon=1.001, key=k1),
            WifiMeasure(lat=1.002, lon=1.005, key=k1),
            WifiMeasure(lat=1.003, lon=1.009, key=k1),
            # a wifi with a prior known position
            Wifi(lat=2.0, lon=2.0, key=k2,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=2.01, lon=2, key=k2),
            WifiMeasure(lat=2.07, lon=2, key=k2),
            # a wifi with a very different prior position
            Wifi(lat=1.0, lon=1.0, key=k3,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=3.0, lon=3.0, key=k3),
            WifiMeasure(lat=-3.0, lon=3.0, key=k3),
            # another wifi with a prior known position (and negative lat)
            Wifi(lat=-4.0, lon=4.0, key=k4,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=-4.1, lon=4, key=k4),
            WifiMeasure(lat=-4.16, lon=4, key=k4),
            # an already blacklisted wifi
            WifiBlacklist(key=k5),
            WifiMeasure(lat=5.0, lon=5.0, key=k5),
            WifiMeasure(lat=5.1, lon=5.0, key=k5),
            # a wifi with an old different record we ignore, position
            # estimate has been updated since
            Wifi(lat=6.0, lon=6.0, key=k6,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=6.9, lon=6.9, key=k6, time=long_ago),
            WifiMeasure(lat=6.0, lon=6.0, key=k6),
            WifiMeasure(lat=6.001, lon=6.0, key=k6),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        black = session.query(WifiBlacklist).all()
        self.assertEqual(set([b.key for b in black]), set([k2, k3, k4, k5]))

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 14)
        self.assertEqual(set([m.key for m in measures]), keys)

        # test duplicate call
        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), 0)

        self.check_stats(
            total=6,
            timer=[
                # We made duplicate calls
                ('task.data.location_update_wifi', 2),
                # One of those would've scheduled a remove_wifi task
                ('task.data.remove_wifi', 1)
            ],
            gauge=[
                ('task.data.location_update_wifi.new_measures_1_100', 2),
            ])

    def test_blacklist_temporary_and_permanent(self):
        session = self.db_master_session

        # This test simulates a wifi that moves once a month, for 2 years.
        # The first 2 * PERMANENT_BLACKLIST_THRESHOLD (12) moves should be
        # temporary, forgotten after a week; after that it should be
        # permanently blacklisted.

        now = util.utcnow()
        # Station moves between these 4 points, all in the USA:
        points = [
            # NYC
            (40.0, -74.0),
            # SF
            (37.0, -122.0),
            # Seattle
            (47.0, -122.0),
            # Miami
            (25.0, -80.0),
        ]

        N = 4 * PERMANENT_BLACKLIST_THRESHOLD
        for month in range(0, N):
            days_ago = (N - (month + 1)) * 30
            time = now - timedelta(days=days_ago)
            time_enc = encode_datetime(time)

            measure = dict(key="ab1234567890",
                           time=time_enc,
                           lat=points[month % 4][0],
                           lon=points[month % 4][1])

            # insert_result is num-accepted-measures, override
            # utcnow to set creation date
            insert_result = insert_measures_wifi.delay(
                [measure], utcnow=time_enc)

            # update_result is (num-stations, num-moving-stations)
            update_result = location_update_wifi.delay(min_new=1)

            # Assuming PERMANENT_BLACKLIST_THRESHOLD == 6:
            #
            # 0th insert will create the station
            # 1st insert will create first blacklist entry, delete station
            # 2nd insert will recreate the station at new position
            # 3rd insert will update blacklist, re-delete station
            # 4th insert will recreate the station at new position
            # 5th insert will update blacklist, re-delete station
            # 6th insert will recreate the station at new position
            # ...
            # 11th insert will make blacklisting permanent, re-delete station
            # 12th insert will not recreate station
            # 13th insert will not recreate station
            # ...
            # 23rd insert will not recreate station

            bl = session.query(WifiBlacklist).all()
            if month == 0:
                self.assertEqual(len(bl), 0)
            else:
                self.assertEqual(len(bl), 1)
                # force the blacklist back in time to whenever the
                # measure was supposedly inserted.
                bl = bl[0]
                bl.time = time
                session.add(bl)
                session.commit()

            if month < N / 2:
                # We still haven't exceeded the threshold, so the
                # measurement was admitted.
                self.assertEqual(insert_result.get(), 1)
                self.assertEqual(session.query(WifiMeasure).count(), month + 1)
                if month % 2 == 0:
                    # The station was (re)created.
                    self.assertEqual(update_result.get(), (1, 0))
                    # One wifi record should exist.
                    self.assertEqual(session.query(Wifi).count(), 1)
                else:
                    # The station existed and was seen moving,
                    # thereby activating the blacklist.
                    self.assertEqual(update_result.get(), (1, 1))
                    self.assertEqual(bl.count, ((month + 1) / 2))
                    self.assertEqual(session.query(WifiBlacklist).count(), 1)
                    self.assertEqual(session.query(Wifi).count(), 0)

                    # Try adding one more measurement 1 day later
                    # to be sure it is dropped by the now-active blacklist.
                    next_day = encode_datetime(time + timedelta(days=1))
                    measure['time'] = next_day
                    self.assertEqual(
                        0, insert_measures_wifi.delay([measure],
                                                      utcnow=next_day).get())

            else:
                # Blacklist has exceeded threshold, gone to "permanent" mode,
                # so no measures accepted, no stations seen.
                self.assertEqual(insert_result.get(), 0)
                self.assertEqual(update_result.get(), 0)

    def test_blacklist_time_used_as_creation_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLACKLIST_DURATION - timedelta(days=1)
        session = self.db_master_session

        wifi_key = "ab1234567890"

        session.add(WifiBlacklist(time=last_week, key=wifi_key))
        session.flush()

        # add a new entry for the previously blacklisted wifi
        measure = dict(lat=PARIS_LAT, lon=PARIS_LON, key=wifi_key)
        insert_measures_wifi.delay([measure]).get()

        # the wifi was inserted again
        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)

        # and the creation date was set to the date of the blacklist entry
        self.assertEqual(wifis[0].created, last_week)

    def test_insert_measures(self):
        session = self.db_master_session
        time = util.utcnow() - timedelta(days=1)

        session.add(Wifi(key="ab1234567890"))
        session.add(Score(userid=1, key=SCORE_TYPE['new_wifi'], value=7))
        session.flush()

        measure = dict(
            created=encode_datetime(time), lat=1.0, lon=2.0,
            time=encode_datetime(time), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=-1,
            heading=52.9,
            speed=158.5,
        )
        entries = [
            {"key": "ab1234567890", "channel": 11, "signal": -80},
            {"key": "ab1234567890", "channel": 3, "signal": -90},
            {"key": "ab1234567890", "channel": 3, "signal": -80},
            {"key": "cd3456789012", "channel": 3, "signal": -90},
        ]
        for e in entries:
            e.update(measure)
        result = insert_measures_wifi.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 4)
        self.assertEqual(set([m.key for m in measures]), set(["ab1234567890",
                                                              "cd3456789012"]))
        self.assertEqual(set([m.channel for m in measures]), set([3, 11]))
        self.assertEqual(set([m.signal for m in measures]), set([-80, -90]))
        self.assertEqual(set([m.heading or m in measures]), set([52.9]))
        self.assertEqual(set([m.speed or m in measures]), set([158.5]))

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 2)
        self.assertEqual(set([w.key for w in wifis]), set(["ab1234567890",
                                                           "cd3456789012"]))
        self.assertEqual(set([w.new_measures for w in wifis]), set([1, 3]))
        self.assertEqual(set([w.total_measures for w in wifis]), set([1, 3]))

        scores = session.query(Score).all()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].key, SCORE_TYPE['new_wifi'])
        self.assertEqual(scores[0].value, 8)

        # test duplicate execution
        result = insert_measures_wifi.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)
        # TODO this task isn't idempotent yet
        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 8)

    def test_insert_measures_overflow(self):
        session = self.db_master_session
        key = "001234567890"

        measures = [dict(key=key,
                         lat=1.0 + i * 0.0000001,
                         lon=2.0 + i * 0.0000001) for i in range(3)]

        result = insert_measures_wifi.delay(measures)
        self.assertEqual(result.get(), 3)

        result = insert_measures_wifi.delay(measures, max_measures_per_wifi=3)
        self.assertEqual(result.get(), 0)

        result = insert_measures_wifi.delay(measures, max_measures_per_wifi=10)
        self.assertEqual(result.get(), 3)

        result = insert_measures_wifi.delay(measures, max_measures_per_wifi=3)
        self.assertEqual(result.get(), 0)

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 6)

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)
        self.assertEqual(wifis[0].total_measures, 6)

    def test_location_update_wifi(self):
        now = util.utcnow()
        before = now - timedelta(days=1)
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "cd1234567890"
        data = [
            Wifi(key=k1, new_measures=3, total_measures=3),
            WifiMeasure(lat=1.0, lon=1.0, key=k1),
            WifiMeasure(lat=1.002, lon=1.003, key=k1),
            WifiMeasure(lat=1.004, lon=1.006, key=k1),
            Wifi(key=k2, lat=2.0, lon=2.0,
                 new_measures=2, total_measures=4),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old measures are skipped
            WifiMeasure(lat=-1.0, lon=-1.0, key=k2, created=before),
            WifiMeasure(lat=-1.0, lon=-1.0, key=k2, created=before),
            WifiMeasure(lat=2.002, lon=2.004, key=k2, created=now),
            WifiMeasure(lat=2.002, lon=2.004, key=k2, created=now),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), (2, 0))
        self.check_stats(
            total=2,
            timer=['task.data.location_update_wifi'],
            gauge=['task.data.location_update_wifi.new_measures_1_100'],
        )

        wifis = dict(session.query(Wifi.key, Wifi).all())
        self.assertEqual(set(wifis.keys()), set([k1, k2]))

        self.assertEqual(wifis[k1].lat, 1.002)
        self.assertEqual(wifis[k1].lon, 1.003)
        self.assertEqual(wifis[k1].new_measures, 0)

        self.assertEqual(wifis[k2].lat, 2.001)
        self.assertEqual(wifis[k2].lon, 2.002)
        self.assertEqual(wifis[k2].new_measures, 0)

    def test_max_min_range_update(self):
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "cd1234567890"
        data = [
            Wifi(key=k1, new_measures=2, total_measures=2),
            WifiMeasure(lat=1.0, lon=1.0, key=k1),
            WifiMeasure(lat=1.002, lon=1.004, key=k1),
            Wifi(key=k2, lat=2.0, lon=-2.0,
                 max_lat=2.001, min_lat=1.999,
                 max_lon=-1.999, min_lon=-2.001,
                 new_measures=2, total_measures=4),
            WifiMeasure(lat=2.002, lon=-2.004, key=k2),
            WifiMeasure(lat=1.998, lon=-1.996, key=k2),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), (2, 0))

        wifis = dict(session.query(Wifi.key, Wifi).all())
        self.assertEqual(set(wifis.keys()), set([k1, k2]))

        self.assertEqual(wifis[k1].lat, 1.001)
        self.assertEqual(wifis[k1].max_lat, 1.002)
        self.assertEqual(wifis[k1].min_lat, 1.0)
        self.assertEqual(wifis[k1].lon, 1.002)
        self.assertEqual(wifis[k1].max_lon, 1.004)
        self.assertEqual(wifis[k1].min_lon, 1.0)

        self.assertEqual(wifis[k2].lat, 2.0)
        self.assertEqual(wifis[k2].max_lat, 2.002)
        self.assertEqual(wifis[k2].min_lat, 1.998)
        self.assertEqual(wifis[k2].lon, -2.0)
        self.assertEqual(wifis[k2].max_lon, -1.996)
        self.assertEqual(wifis[k2].min_lon, -2.004)

        # independent calculation: the k1 bounding box is
        # (1.000, 1.000) to (1.002, 1.004), with centroid
        # at (1.001, 1.002); worst distance from centroid
        # to any corner is 249m
        self.assertEqual(wifis[k1].range, 249)

        # independent calculation: the k2 bounding box is
        # (1.998, -2.004) to (2.002, -1.996), with centroid
        # at (2.000, 2.000); worst distance from centroid
        # to any corner is 497m
        self.assertEqual(wifis[k2].range, 497)

    def test_remove_wifi(self):
        session = self.db_master_session
        measures = []
        wifi_keys = [{'key': "a%s1234567890" % i} for i in range(5)]
        m1 = 1.0
        m2 = 2.0
        for key in wifi_keys:
            key = key['key']
            measures.append(Wifi(key=key))
            measures.append(WifiMeasure(lat=m1, lon=m1, key=key))
            measures.append(WifiMeasure(lat=m2, lon=m2, key=key))
        session.add_all(measures)
        session.flush()

        result = remove_wifi.delay(wifi_keys[:2])
        self.assertEqual(result.get(), 2)

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 3)

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), 3)

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), 0)

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 0)


class TestSubmitErrors(CeleryTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_master.engine)
        super(TestSubmitErrors, self).tearDown()

    def test_database_error(self):
        session = self.db_master_session

        stmt = text("drop table wifi;")
        session.execute(stmt)

        entries = [
            {"lat": 1.0, "lon": 2.0,
             "key": "ab:12:34:56:78:90", "channel": 11},
            {"lat": 1.0, "lon": 2.0,
             "key": "ab:12:34:56:78:90", "channel": 3},
            {"lat": 1.0, "lon": 2.0,
             "key": "ab:12:34:56:78:90", "channel": 3},
            {"lat": 1.0, "lon": 2.0,
             "key": "cd:12:34:56:78:90", "channel": 3},
        ]

        try:
            insert_measures_wifi.delay(entries)
        except ProgrammingError:
            pass
        except Exception as exc:
            self.fail("Unexpected exception caught: %s" % repr(exc))

        find_msg = self.find_heka_messages
        messages = find_msg('sentry', RAVEN_ERROR, field_name='msg')
        self.assertEquals(len(messages), 4)

        payload = messages[0].payload
        # duplicate raven.base.RavenClient.decode
        data = json.loads(zlib.decompress(base64.b64decode(payload)))
        sentry_exc = data['sentry.interfaces.Exception']

        self.assertEqual(sentry_exc['module'], ProgrammingError.__module__)
        self.assertEqual(sentry_exc['type'], 'ProgrammingError')
