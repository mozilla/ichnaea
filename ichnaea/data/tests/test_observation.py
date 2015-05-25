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

    def _compare_sets(self, one, two):
        self.assertEqual(set(one), set(two))

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
            {'mcc': mcc, 'mnc': 2, 'signal': -100},

            {'mcc': mcc, 'mnc': 2, 'lac': 3, 'cid': 4, 'psc': 5, 'asu': 8},
            {'mcc': mcc, 'mnc': 2, 'lac': 3, 'cid': 4, 'psc': 5, 'asu': 8},
            {'mcc': mcc, 'mnc': 2, 'lac': 3, 'cid': 4, 'psc': 5, 'asu': 15},
            {'mcc': mcc, 'mnc': 2, 'lac': 3, 'cid': 7, 'psc': 5},
        ]
        for e in entries:
            e.update(obs)

        result = insert_measures_cell.delay(entries, userid=user.id)

        self.assertEqual(result.get(), 4)
        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 4)
        self._compare_sets([o.mcc for o in observations], [mcc])
        self._compare_sets([o.mnc for o in observations], [2])
        self._compare_sets([o.asu for o in observations], [None, 8, 15])
        self._compare_sets([o.psc for o in observations], [5])
        self._compare_sets([o.signal for o in observations], [None])

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 2)
        self._compare_sets([c.mcc for c in cells], [mcc])
        self._compare_sets([c.mnc for c in cells], [2])
        self._compare_sets([c.lac for c in cells], [3])
        self._compare_sets([c.cid for c in cells], [4, 7])
        self._compare_sets([c.psc for c in cells], [5])
        self._compare_sets([c.new_measures for c in cells], [1, 5])
        self._compare_sets([c.total_measures for c in cells], [1, 8])

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
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': constants.MAX_LAC_ALL + 1,
             'cid': constants.MAX_CID_ALL + 1, 'psc': 5, 'asu': 8},
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': None,
             'cid': None, 'psc': 5, 'asu': 8},
        ]
        for e in entries:
            e.update(obs)

        result = insert_measures_cell.delay(entries, userid=1)
        self.assertEqual(result.get(), 2)

        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 2)
        self._compare_sets([o.lac for o in observations], [None])
        self._compare_sets([o.cid for o in observations], [None])

        # Nothing should change in the initially created Cell record
        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        self._compare_sets([c.new_measures for c in cells], [2])
        self._compare_sets([c.total_measures for c in cells], [5])

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
            {'asu': 8, 'signal': -70, 'ta': 32},
            {'asu': -10, 'signal': -300, 'ta': -10},
            {'asu': 256, 'signal': 16, 'ta': 128},
        ]
        for e in entries:
            e.update(obs)

        result = insert_measures_cell.delay(entries)
        self.assertEqual(result.get(), 3)

        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 3)
        self._compare_sets([o.asu for o in observations], [None, 8])
        self._compare_sets([o.signal for o in observations], [None, -70])
        self._compare_sets([o.ta for o in observations], [None, 32])


class TestWifi(ObservationTestCase):

    def test_blacklist(self):
        utcnow = util.utcnow()
        session = self.session
        bad_key = 'ab1234567890'
        good_key = 'cd1234567890'
        black = WifiBlacklist(time=utcnow, count=1, key=bad_key)
        session.add(black)
        session.flush()
        obs = dict(lat=1, lon=2)
        entries = [{'key': good_key}, {'key': good_key}, {'key': bad_key}]
        for e in entries:
            e.update(obs)

        result = insert_measures_wifi.delay(entries)
        self.assertEqual(result.get(), 2)

        observations = session.query(WifiObservation).all()
        self.assertEqual(len(observations), 2)
        self._compare_sets([o.key for o in observations], [good_key])

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)
        self._compare_sets([w.key for w in wifis], [good_key])

        self.check_statcounter(StatKey.wifi, 2)
        self.check_statcounter(StatKey.unique_wifi, 1)

    def test_blacklist_time_used_as_creation_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLACKLIST_DURATION - timedelta(days=1)
        session = self.session

        wifi_key = 'ab1234567890'

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

        session.add(Wifi(key='ab1234567890',
                         new_measures=0, total_measures=0))
        user = User(nickname=u'test')
        session.add(user)
        session.flush()

        obs = dict(
            created=time, lat=1.0, lon=2.0,
            time=time, accuracy=None, altitude=None,
            altitude_accuracy=None, radio=None,
            heading=52.9, speed=158.5,
        )
        entries = [
            {'key': 'ab1234567890', 'channel': 11, 'signal': -80},
            {'key': 'ab1234567890', 'channel': 3, 'signal': -90},
            {'key': 'ab1234567890', 'channel': 3, 'signal': -80},
            {'key': 'cd3456789012', 'channel': 3, 'signal': -90},
        ]
        for e in entries:
            e.update(obs)
        result = insert_measures_wifi.delay(entries, userid=user.id)
        self.assertEqual(result.get(), 4)

        observations = session.query(WifiObservation).all()
        self.assertEqual(len(observations), 4)
        self._compare_sets([o.key for o in observations],
                           ['ab1234567890', 'cd3456789012'])
        self._compare_sets([o.channel for o in observations], [3, 11])
        self._compare_sets([o.signal for o in observations], [-80, -90])
        self._compare_sets([o.heading or o in observations], [52.9])
        self._compare_sets([o.speed or o in observations], [158.5])

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 2)
        self._compare_sets([w.key for w in wifis],
                           ['ab1234567890', 'cd3456789012'])
        self._compare_sets([w.new_measures for w in wifis], [1, 3])
        self._compare_sets([w.total_measures for w in wifis], [1, 3])

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

        stmt = text('drop table wifi;')
        session.execute(stmt)

        entries = [
            {'lat': 1.0, 'lon': 2.0,
             'key': 'ab:12:34:56:78:90', 'channel': 11},
            {'lat': 1.0, 'lon': 2.0,
             'key': 'ab:12:34:56:78:90', 'channel': 3},
            {'lat': 1.0, 'lon': 2.0,
             'key': 'ab:12:34:56:78:90', 'channel': 3},
            {'lat': 1.0, 'lon': 2.0,
             'key': 'cd:12:34:56:78:90', 'channel': 3},
        ]

        try:
            insert_measures_wifi.delay(entries)
        except ProgrammingError:
            pass
        except Exception as exc:
            self.fail('Unexpected exception caught: %s' % repr(exc))

        self.check_raven([('ProgrammingError', 1)])

        self.check_statcounter(StatKey.wifi, 0)
        self.check_statcounter(StatKey.unique_wifi, 0)
