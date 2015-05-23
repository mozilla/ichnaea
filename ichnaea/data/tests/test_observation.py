from datetime import timedelta

from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text

from ichnaea.constants import (
    TEMPORARY_BLACKLIST_DURATION,
)
from ichnaea.data.tasks import (
    insert_measures_cell,
    insert_measures_wifi,
)
from ichnaea.models import (
    constants,
    Cell,
    CellBlacklist,
    CellObservation,
    Radio,
    Score,
    ScoreKey,
    StatCounter,
    StatKey,
    User,
    ValidCellKeySchema,
    Wifi,
    WifiBlacklist,
    WifiObservation,
)
from ichnaea.tests.base import (
    CeleryTestCase,
    PARIS_LAT, PARIS_LON, FRANCE_MCC,
)
from ichnaea import util


class ObservationTestCase(CeleryTestCase):

    def check_statcounter(self, stat_key, value):
        stat_counter = StatCounter(stat_key, util.utcnow())
        self.assertEqual(stat_counter.get(self.redis_client), value)


class TestCell(ObservationTestCase):

    def test_blacklist(self):
        now = util.utcnow()
        session = self.session

        observations = [dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=i, psc=5,
                             radio=int(Radio.gsm),
                             lat=PARIS_LAT + i * 0.0000001,
                             lon=PARIS_LON + i * 0.0000001)
                        for i in range(1, 4)]

        black = CellBlacklist(
            mcc=FRANCE_MCC, mnc=2, lac=3, cid=1,
            radio=Radio.gsm, time=now, count=1,
        )
        session.add(black)
        session.flush()

        result = insert_measures_cell.delay(observations)
        self.assertEqual(result.get(), 2)

        cell_observations = session.query(CellObservation).all()
        self.assertEqual(len(cell_observations), 2)

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 2)

        self.check_statcounter(StatKey.cell, 2)
        self.check_statcounter(StatKey.unique_cell, 2)

    def test_blacklist_time_used_as_creation_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLACKLIST_DURATION - timedelta(days=1)
        session = self.session

        cell_key = {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 3, 'cid': 1}

        session.add(CellBlacklist(time=last_week, count=1,
                                  radio=Radio.gsm, **cell_key))
        session.flush()

        # add a new entry for the previously blacklisted cell
        obs = dict(lat=PARIS_LAT, lon=PARIS_LON,
                   radio=int(Radio.gsm), **cell_key)
        insert_measures_cell.delay([obs]).get()

        # the cell was inserted again
        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)

        # and the creation date was set to the date of the blacklist entry
        self.assertEqual(cells[0].created, last_week)

        self.check_statcounter(StatKey.cell, 1)
        self.check_statcounter(StatKey.unique_cell, 0)

    def test_insert_observations(self):
        session = self.session
        time = util.utcnow() - timedelta(days=1)
        mcc = FRANCE_MCC

        session.add(Cell(radio=Radio.gsm, mcc=mcc, mnc=2, lac=3,
                         cid=4, psc=5, new_measures=2,
                         total_measures=5))
        user = User(nickname=u'test')
        session.add(user)
        session.flush()

        obs = dict(
            created=time,
            lat=PARIS_LAT,
            lon=PARIS_LON,
            time=time, accuracy=0, altitude=0,
            altitude_accuracy=0, radio=int(Radio.gsm),
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

        result = insert_measures_cell.delay(entries, userid=user.id)

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

        score_queue = self.celery_app.data_queues['update_score']
        scores = score_queue.dequeue()
        self.assertEqual(len(scores), 1)
        score = scores[0]
        self.assertEqual(score['hashkey'].userid, user.id)
        self.assertEqual(score['hashkey'].key, ScoreKey.new_cell)
        self.assertEqual(score['value'], 1)

        self.check_statcounter(StatKey.cell, 4)
        self.check_statcounter(StatKey.unique_cell, 1)

        # test duplicate execution
        result = insert_measures_cell.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)
        # TODO this task isn't idempotent yet
        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 8)

    def test_insert_observations_invalid_lac(self):
        session = self.session
        schema = ValidCellKeySchema()
        time = util.utcnow() - timedelta(days=1)
        today = util.utcnow().date()

        session.add(Cell(radio=Radio.gsm, mcc=FRANCE_MCC, mnc=2,
                         lac=3, cid=4, new_measures=2, total_measures=5))
        session.add(Score(key=ScoreKey.new_cell,
                          userid=1, time=today, value=7))
        session.flush()

        obs = dict(
            created=time,
            lat=PARIS_LAT,
            lon=PARIS_LON,
            time=time, accuracy=0, altitude=0,
            altitude_accuracy=0, radio=int(Radio.gsm))
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

    def test_insert_observations_out_of_range(self):
        session = self.session
        time = util.utcnow() - timedelta(days=1)

        obs = dict(
            created=time,
            lat=PARIS_LAT,
            lon=PARIS_LON,
            time=time, accuracy=0, altitude=0,
            altitude_accuracy=0, radio=int(Radio.gsm), mcc=FRANCE_MCC,
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


class TestWifi(ObservationTestCase):

    def test_blacklist(self):
        utcnow = util.utcnow()
        session = self.session
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

        self.check_statcounter(StatKey.wifi, 2)
        self.check_statcounter(StatKey.unique_wifi, 1)

    def test_blacklist_time_used_as_creation_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLACKLIST_DURATION - timedelta(days=1)
        session = self.session

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
        self.check_statcounter(StatKey.unique_wifi, 0)

    def test_insert_observations(self):
        session = self.session
        time = util.utcnow() - timedelta(days=1)

        session.add(Wifi(key="ab1234567890",
                         new_measures=0, total_measures=0))
        user = User(nickname=u'test')
        session.add(user)
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
        result = insert_measures_wifi.delay(entries, userid=user.id)
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

        score_queue = self.celery_app.data_queues['update_score']
        scores = score_queue.dequeue()
        self.assertEqual(len(scores), 1)
        score = scores[0]
        self.assertEqual(score['hashkey'].userid, user.id)
        self.assertEqual(score['hashkey'].key, ScoreKey.new_wifi)
        self.assertEqual(score['value'], 1)

        self.check_statcounter(StatKey.wifi, 4)
        self.check_statcounter(StatKey.unique_wifi, 1)

        # test duplicate execution
        result = insert_measures_wifi.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)
        # TODO this task isn't idempotent yet
        observations = session.query(WifiObservation).all()
        self.assertEqual(len(observations), 8)


class TestSubmitErrors(ObservationTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_rw.engine)
        super(TestSubmitErrors, self).tearDown()

    def test_database_error(self):
        session = self.session

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

        self.check_raven([('ProgrammingError', 1)])

        self.check_statcounter(StatKey.wifi, 0)
        self.check_statcounter(StatKey.unique_wifi, 0)
