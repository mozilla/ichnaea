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
from ichnaea.models.content import (
    Score,
    ScoreKey,
)
from ichnaea.data import constants
from ichnaea.data.schema import ValidCellKeySchema
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
    CellObservation,
    RADIO_TYPE,
    Wifi,
    WifiBlacklist,
    WifiObservation,
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
        observations = [
            CellObservation(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(10)
            for ctr in [cell * big]
            for (xd, yd) in [(small, small),
                             (small, -small),
                             (-small, small),
                             (-small, -small)]
        ]
        session.add_all(observations)

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
                                            batch=len(observations))
        self.assertEqual(result.get(), (len(cells), 0))
        scan_lacs.delay()

    def test_blacklist(self):
        now = util.utcnow()
        session = self.db_master_session

        observations = [dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=i, psc=5,
                             radio=RADIO_TYPE['gsm'],
                             lat=PARIS_LAT + i * 0.0000001,
                             lon=PARIS_LON + i * 0.0000001)
                        for i in range(1, 4)]

        black = CellBlacklist(
            mcc=FRANCE_MCC, mnc=2, lac=3, cid=1,
            radio=RADIO_TYPE['gsm'], time=now, count=1,
        )
        session.add(black)
        session.flush()

        result = insert_measures_cell.delay(observations)
        self.assertEqual(result.get(), 2)

        cell_observations = session.query(CellObservation).all()
        self.assertEqual(len(cell_observations), 2)

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
            CellObservation(lat=1.001, lon=1.001, **k1),
            CellObservation(lat=1.002, lon=1.005, **k1),
            CellObservation(lat=1.003, lon=1.009, **k1),
            # a cell with a prior known position
            Cell(lat=2.0, lon=2.0,
                 new_measures=2, total_measures=1, **k2),
            CellObservation(lat=2.0, lon=2.0, **k2),
            CellObservation(lat=4.0, lon=2.0, **k2),
            # a cell with a very different prior position
            Cell(lat=1.0, lon=1.0,
                 new_measures=2, total_measures=1, **k3),
            CellObservation(lat=3.0, lon=3.0, **k3),
            CellObservation(lat=-3.0, lon=3.0, **k3),
            # another cell with a prior known position (and negative lat)
            Cell(lat=-4.0, lon=4.0,
                 new_measures=2, total_measures=1, **k4),
            CellObservation(lat=-4.0, lon=4.0, **k4),
            CellObservation(lat=-6.0, lon=4.0, **k4),
            # an already blacklisted cell
            CellBlacklist(time=now, count=1, **k5),
            CellObservation(lat=5.0, lon=5.0, **k5),
            CellObservation(lat=8.0, lon=5.0, **k5),
            # a cell with an old different record we ignore, position
            # estimate has been updated since
            Cell(lat=6.0, lon=6.0,
                 new_measures=2, total_measures=1, **k6),
            CellObservation(lat=6.9, lon=6.9, time=long_ago, **k6),
            CellObservation(lat=6.0, lon=6.0, **k6),
            CellObservation(lat=6.001, lon=6, **k6),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        black = session.query(CellBlacklist).all()
        self.assertEqual(set([to_cellkey(b) for b in black]),
                         set([CellKey(**k) for k in [k2, k3, k4, k5]]))

        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 14)
        self.assertEqual(set([to_cellkey(obs) for obs in observations]), keys)

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

            obs = dict(radio=RADIO_TYPE['gsm'],
                       mcc=USA_MCC, mnc=ATT_MNC, lac=456, cid=123,
                       time=time,
                       lat=points[month % 4][0],
                       lon=points[month % 4][1])

            # insert_result is num-accepted-observations, override
            # utcnow to set creation date
            insert_result = insert_measures_cell.delay(
                [obs], utcnow=time)

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
                # observation was supposedly inserted.
                bl = bl[0]
                bl.time = time
                session.add(bl)
                session.commit()

            if month < N / 2:
                # We still haven't exceeded the threshold, so the
                # observation was admitted.
                self.assertEqual(insert_result.get(), 1)
                self.assertEqual(session.query(CellObservation).count(),
                                 month + 1)
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

                    # Try adding one more observation 1 day later
                    # to be sure it is dropped by the now-active blacklist.
                    next_day = time + timedelta(days=1)
                    obs['time'] = next_day
                    self.assertEqual(
                        0, insert_measures_cell.delay([obs],
                                                      utcnow=next_day).get())

            else:
                # Blacklist has exceeded threshold, gone to "permanent" mode,
                # so no observation accepted, no stations seen.
                self.assertEqual(insert_result.get(), 0)
                self.assertEqual(update_result.get(), 0)

    def test_blacklist_time_used_as_creation_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLACKLIST_DURATION - timedelta(days=1)
        session = self.db_master_session

        cell_key = {'radio': RADIO_TYPE['gsm'], 'mcc': FRANCE_MCC,
                    'mnc': 2, 'lac': 3, 'cid': 1}

        session.add(CellBlacklist(time=last_week, count=1, **cell_key))
        session.flush()

        # add a new entry for the previously blacklisted cell
        obs = dict(lat=PARIS_LAT, lon=PARIS_LON, **cell_key)
        insert_measures_cell.delay([obs]).get()

        # the cell was inserted again
        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)

        # and the creation date was set to the date of the blacklist entry
        self.assertEqual(cells[0].created, last_week)

    def test_insert_observations(self):
        session = self.db_master_session
        time = util.utcnow() - timedelta(days=1)
        today = util.utcnow().date()
        mcc = FRANCE_MCC

        session.add(Cell(radio=RADIO_TYPE['gsm'], mcc=mcc, mnc=2, lac=3,
                         cid=4, psc=5, new_measures=2,
                         total_measures=5))
        session.add(Score(key=ScoreKey.new_cell,
                          userid=1, time=today, value=7))
        session.flush()

        obs = dict(
            created=time,
            lat=PARIS_LAT,
            lon=PARIS_LON,
            time=time, accuracy=0, altitude=0,
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
            e.update(obs)

        result = insert_measures_cell.delay(entries, userid=1)

        self.assertEqual(result.get(), 4)
        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 4)
        self.assertEqual(set([o.mcc for o in observations]), set([mcc]))
        self.assertEqual(set([o.mnc for o in observations]), set([2]))
        self.assertEqual(set([o.asu for o in observations]), set([-1, 8, 15]))
        self.assertEqual(set([o.psc for o in observations]), set([5]))
        self.assertEqual(set([o.signal for o in observations]), set([0]))

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
        self.assertEqual(scores[0].key, ScoreKey.new_cell)
        self.assertEqual(scores[0].value, 8)

        # test duplicate execution
        result = insert_measures_cell.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)
        # TODO this task isn't idempotent yet
        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 8)

    def test_insert_observations_invalid_lac(self):
        session = self.db_master_session
        schema = ValidCellKeySchema()
        time = util.utcnow() - timedelta(days=1)
        today = util.utcnow().date()

        session.add(Cell(radio=RADIO_TYPE['gsm'], mcc=FRANCE_MCC, mnc=2,
                         lac=3, cid=4, new_measures=2, total_measures=5))
        session.add(Score(key=ScoreKey.new_cell,
                          userid=1, time=today, value=7))
        session.flush()

        obs = dict(
            created=time,
            lat=PARIS_LAT,
            lon=PARIS_LON,
            time=time, accuracy=0, altitude=0,
            altitude_accuracy=0, radio=RADIO_TYPE['gsm'])
        entries = [
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": constants.MAX_LAC_ALL + 1,
             "cid": constants.MAX_CID_ALL + 1, "psc": 5, "asu": 8},
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": schema.fields['lac'].missing,
             "cid": schema.fields['cid'].missing, "psc": 5, "asu": 8},
        ]
        for e in entries:
            e.update(obs)

        result = insert_measures_cell.delay(entries, userid=1)
        self.assertEqual(result.get(), 2)

        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 2)
        self.assertEqual(
            set([o.lac for o in observations]),
            set([schema.fields['lac'].missing]))
        self.assertEqual(
            set([o.cid for o in observations]),
            set([schema.fields['cid'].missing]))

        # Nothing should change in the initially created Cell record
        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        self.assertEqual(set([c.new_measures for c in cells]), set([2]))
        self.assertEqual(set([c.total_measures for c in cells]), set([5]))

    def test_insert_observations_overflow(self):
        session = self.db_master_session

        observations = [dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4, psc=5,
                             radio=RADIO_TYPE['gsm'],
                             lat=PARIS_LAT + i * 0.0000001,
                             lon=PARIS_LON + i * 0.0000001) for i in range(3)]

        result = insert_measures_cell.delay(observations)
        self.assertEqual(result.get(), 3)

        result = insert_measures_cell.delay(
            observations, max_observations_per_cell=3)
        self.assertEqual(result.get(), 0)

        result = insert_measures_cell.delay(
            observations, max_observations_per_cell=10)
        self.assertEqual(result.get(), 3)

        result = insert_measures_cell.delay(
            observations, max_observations_per_cell=3)
        self.assertEqual(result.get(), 0)

        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 6)

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0].total_measures, 6)

    def test_insert_observations_out_of_range(self):
        session = self.db_master_session
        time = util.utcnow() - timedelta(days=1)

        obs = dict(
            created=time,
            lat=PARIS_LAT,
            lon=PARIS_LON,
            time=time, accuracy=0, altitude=0,
            altitude_accuracy=0, radio=RADIO_TYPE['gsm'], mcc=FRANCE_MCC,
            mnc=2, lac=3, cid=4)
        entries = [
            {"asu": 8, "signal": -70, "ta": 32},
            {"asu": -10, "signal": -300, "ta": -10},
            {"asu": 256, "signal": 16, "ta": 128},
        ]
        for e in entries:
            e.update(obs)

        result = insert_measures_cell.delay(entries)
        self.assertEqual(result.get(), 3)

        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 3)
        self.assertEqual(set([o.asu for o in observations]), set([-1, 8]))
        self.assertEqual(set([o.signal for o in observations]), set([0, -70]))
        self.assertEqual(set([o.ta for o in observations]), set([0, 32]))

    def test_location_update_cell(self):
        now = util.utcnow()
        before = now - timedelta(days=1)
        schema = ValidCellKeySchema()
        session = self.db_master_session

        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        k2 = dict(radio=1, mcc=1, mnc=2, lac=6, cid=8)
        k3 = dict(radio=1, mcc=1, mnc=2,
                  lac=schema.fields['lac'].missing,
                  cid=schema.fields['cid'].missing)
        data = [
            Cell(new_measures=3, total_measures=5, **k1),
            CellObservation(lat=1.0, lon=1.0, created=now, **k1),
            CellObservation(lat=1.002, lon=1.003, created=now, **k1),
            CellObservation(lat=1.004, lon=1.006, created=now, **k1),
            # The lac, cid are invalid and should be skipped
            CellObservation(lat=1.5, lon=1.5, created=now, **k3),
            CellObservation(lat=1.502, lon=1.503, created=now, **k3),

            Cell(lat=2.0, lon=2.0,
                 new_measures=2, total_measures=4, **k2),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old observations are skipped
            CellObservation(lat=-1.0, lon=-1.0, created=before, **k2),
            CellObservation(lat=-1.0, lon=-1.0, created=before, **k2),
            CellObservation(lat=2.002, lon=2.004, created=now, **k2),
            CellObservation(lat=2.002, lon=2.004, created=now, **k2),

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
            CellObservation(lat=1.001, lon=-1.003, **k1),
            CellObservation(lat=1.005, lon=-1.007, **k1),
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
        observations = [
            CellObservation(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(6)
            for ctr in [(2 ** cell) * big]
            for (xd, yd) in [(small, small),
                             (small, -small),
                             (-small, small),
                             (-small, -small)]
        ]
        session.add_all(observations)

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
                                            batch=len(observations))
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

        # First batch of cell observations for CID 1
        keys = dict(radio=1, mcc=1, mnc=1, lac=1, cid=1)
        cell = Cell(new_measures=4, total_measures=1, **keys)
        observations = [
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
        ]
        session.add(cell)
        session.add_all(observations)
        session.commit()

        # Periodic location_update_cell runs and updates CID 1
        # to have a location, inserts LAC 1 with new_measures=1
        # which will be picked up by the next scan_lac.
        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (1, 0))

        # Second batch of cell observations for CID 2
        keys['cid'] = 2
        cell = Cell(new_measures=4, total_measures=1, **keys)
        observations = [
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
        ]
        session.add(cell)
        session.add_all(observations)
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
        utcnow = util.utcnow()
        session = self.db_master_session
        bad_key = "ab1234567890"
        good_key = "cd1234567890"
        black = WifiBlacklist(time=utcnow, count=1, key=bad_key)
        session.add(black)
        session.flush()
        obs = dict(lat=1, lon=2)
        entries = [{"key": good_key}, {"key": good_key}, {"key": bad_key}]
        for e in entries:
            e.update(obs)

        result = insert_measures_wifi.delay(entries)
        self.assertEqual(result.get(), 2)

        observations = session.query(WifiObservation).all()
        self.assertEqual(len(observations), 2)
        self.assertEqual(
            set([o.key for o in observations]), set([good_key]))

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
            WifiObservation(lat=1.001, lon=1.001, key=k1),
            WifiObservation(lat=1.002, lon=1.005, key=k1),
            WifiObservation(lat=1.003, lon=1.009, key=k1),
            # a wifi with a prior known position
            Wifi(lat=2.0, lon=2.0, key=k2,
                 new_measures=2, total_measures=1),
            WifiObservation(lat=2.01, lon=2, key=k2),
            WifiObservation(lat=2.07, lon=2, key=k2),
            # a wifi with a very different prior position
            Wifi(lat=1.0, lon=1.0, key=k3,
                 new_measures=2, total_measures=1),
            WifiObservation(lat=3.0, lon=3.0, key=k3),
            WifiObservation(lat=-3.0, lon=3.0, key=k3),
            # another wifi with a prior known position (and negative lat)
            Wifi(lat=-4.0, lon=4.0, key=k4,
                 new_measures=2, total_measures=1),
            WifiObservation(lat=-4.1, lon=4, key=k4),
            WifiObservation(lat=-4.16, lon=4, key=k4),
            # an already blacklisted wifi
            WifiBlacklist(key=k5, time=now, count=1),
            WifiObservation(lat=5.0, lon=5.0, key=k5),
            WifiObservation(lat=5.1, lon=5.0, key=k5),
            # a wifi with an old different record we ignore, position
            # estimate has been updated since
            Wifi(lat=6.0, lon=6.0, key=k6,
                 new_measures=2, total_measures=1),
            WifiObservation(lat=6.9, lon=6.9, key=k6, time=long_ago),
            WifiObservation(lat=6.0, lon=6.0, key=k6),
            WifiObservation(lat=6.001, lon=6.0, key=k6),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        black = session.query(WifiBlacklist).all()
        self.assertEqual(set([b.key for b in black]), set([k2, k3, k4, k5]))

        observations = session.query(WifiObservation).all()
        self.assertEqual(len(observations), 14)
        self.assertEqual(set([o.key for o in observations]), keys)

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

            obs = dict(key="ab1234567890",
                       time=time,
                       lat=points[month % 4][0],
                       lon=points[month % 4][1])

            # insert_result is num-accepted-observations, override
            # utcnow to set creation date
            insert_result = insert_measures_wifi.delay(
                [obs], utcnow=time)

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
                # observation was supposedly inserted.
                bl = bl[0]
                bl.time = time
                session.add(bl)
                session.commit()

            if month < N / 2:
                # We still haven't exceeded the threshold, so the
                # observation was admitted.
                self.assertEqual(insert_result.get(), 1)
                self.assertEqual(session.query(WifiObservation).count(),
                                 month + 1)
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

                    # Try adding one more observation 1 day later
                    # to be sure it is dropped by the now-active blacklist.
                    next_day = time + timedelta(days=1)
                    obs['time'] = next_day
                    self.assertEqual(
                        0, insert_measures_wifi.delay([obs],
                                                      utcnow=next_day).get())

            else:
                # Blacklist has exceeded threshold, gone to "permanent" mode,
                # so no observation accepted, no stations seen.
                self.assertEqual(insert_result.get(), 0)
                self.assertEqual(update_result.get(), 0)

    def test_blacklist_time_used_as_creation_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLACKLIST_DURATION - timedelta(days=1)
        session = self.db_master_session

        wifi_key = "ab1234567890"

        session.add(WifiBlacklist(time=last_week, count=1, key=wifi_key))
        session.flush()

        # add a new entry for the previously blacklisted wifi
        obs = dict(lat=PARIS_LAT, lon=PARIS_LON, key=wifi_key)
        insert_measures_wifi.delay([obs]).get()

        # the wifi was inserted again
        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)

        # and the creation date was set to the date of the blacklist entry
        self.assertEqual(wifis[0].created, last_week)

    def test_insert_observations(self):
        session = self.db_master_session
        time = util.utcnow() - timedelta(days=1)
        today = util.utcnow().date()

        session.add(Wifi(key="ab1234567890",
                         new_measures=0, total_measures=0))
        session.add(Score(key=ScoreKey.new_wifi,
                          userid=1, time=today, value=7))
        session.flush()

        obs = dict(
            created=time, lat=1.0, lon=2.0,
            time=time, accuracy=0, altitude=0,
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
            e.update(obs)
        result = insert_measures_wifi.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)

        observations = session.query(WifiObservation).all()
        self.assertEqual(len(observations), 4)
        self.assertEqual(set([o.key for o in observations]),
                         set(["ab1234567890", "cd3456789012"]))
        self.assertEqual(set([o.channel for o in observations]), set([3, 11]))
        self.assertEqual(set([o.signal for o in observations]),
                         set([-80, -90]))
        self.assertEqual(set([o.heading or o in observations]), set([52.9]))
        self.assertEqual(set([o.speed or o in observations]), set([158.5]))

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 2)
        self.assertEqual(set([w.key for w in wifis]), set(["ab1234567890",
                                                           "cd3456789012"]))
        self.assertEqual(set([w.new_measures for w in wifis]), set([1, 3]))
        self.assertEqual(set([w.total_measures for w in wifis]), set([1, 3]))

        scores = session.query(Score).all()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].key, ScoreKey.new_wifi)
        self.assertEqual(scores[0].value, 8)

        # test duplicate execution
        result = insert_measures_wifi.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)
        # TODO this task isn't idempotent yet
        observations = session.query(WifiObservation).all()
        self.assertEqual(len(observations), 8)

    def test_insert_observations_overflow(self):
        session = self.db_master_session
        key = "001234567890"

        observations = [dict(key=key,
                             lat=1.0 + i * 0.0000001,
                             lon=2.0 + i * 0.0000001) for i in range(3)]

        result = insert_measures_wifi.delay(observations)
        self.assertEqual(result.get(), 3)

        result = insert_measures_wifi.delay(
            observations, max_observations_per_wifi=3)
        self.assertEqual(result.get(), 0)

        result = insert_measures_wifi.delay(
            observations, max_observations_per_wifi=10)
        self.assertEqual(result.get(), 3)

        result = insert_measures_wifi.delay(
            observations, max_observations_per_wifi=3)
        self.assertEqual(result.get(), 0)

        observations = session.query(WifiObservation).all()
        self.assertEqual(len(observations), 6)

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
            WifiObservation(lat=1.0, lon=1.0, key=k1, created=now),
            WifiObservation(lat=1.002, lon=1.003, key=k1, created=now),
            WifiObservation(lat=1.004, lon=1.006, key=k1, created=now),
            Wifi(key=k2, lat=2.0, lon=2.0,
                 new_measures=2, total_measures=4),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old observations are skipped
            WifiObservation(lat=-1.0, lon=-1.0, key=k2, created=before),
            WifiObservation(lat=-1.0, lon=-1.0, key=k2, created=before),
            WifiObservation(lat=2.002, lon=2.004, key=k2, created=now),
            WifiObservation(lat=2.002, lon=2.004, key=k2, created=now),
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
            WifiObservation(lat=1.0, lon=1.0, key=k1),
            WifiObservation(lat=1.002, lon=1.004, key=k1),
            Wifi(key=k2, lat=2.0, lon=-2.0,
                 max_lat=2.001, min_lat=1.999,
                 max_lon=-1.999, min_lon=-2.001,
                 new_measures=2, total_measures=4),
            WifiObservation(lat=2.002, lon=-2.004, key=k2),
            WifiObservation(lat=1.998, lon=-1.996, key=k2),
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
        observations = []
        wifi_keys = [{'key': "a%s1234567890" % i} for i in range(5)]
        m1 = 1.0
        m2 = 2.0
        for key in wifi_keys:
            key = key['key']
            observations.append(Wifi(key=key))
            observations.append(WifiObservation(lat=m1, lon=m1, key=key))
            observations.append(WifiObservation(lat=m2, lon=m2, key=key))
        session.add_all(observations)
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
