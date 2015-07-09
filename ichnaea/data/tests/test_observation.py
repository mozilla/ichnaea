from datetime import timedelta

from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text

from ichnaea.constants import (
    TEMPORARY_BLACKLIST_DURATION,
)
from ichnaea.data.tasks import (
    insert_measures_cell,
    insert_measures_wifi,
    update_cell,
    update_wifi,
)
from ichnaea.models import (
    constants,
    Cell,
    CellBlacklist,
    Radio,
    Score,
    ScoreKey,
    StatCounter,
    StatKey,
    User,
    Wifi,
    WifiBlacklist,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)
from ichnaea import util


class ObservationTestCase(CeleryTestCase):

    def _compare_sets(self, one, two):
        self.assertEqual(set(one), set(two))

    def check_statcounter(self, stat_key, value):
        stat_counter = StatCounter(stat_key, util.utcnow())
        self.assertEqual(stat_counter.get(self.redis_client), value)


class TestCell(ObservationTestCase):

    def setUp(self):
        super(TestCell, self).setUp()
        self.data_queue = self.celery_app.data_queues['update_cell']

    def test_blacklist(self):
        now = util.utcnow()

        cell = CellFactory.build()
        observations = [dict(radio=int(cell.radio), mcc=cell.mcc,
                             mnc=cell.mnc, lac=cell.lac, cid=cell.cid + i,
                             psc=cell.psc,
                             lat=cell.lat + i * 0.0000001,
                             lon=cell.lon + i * 0.0000001)
                        for i in range(1, 4)]

        black = CellBlacklist(
            radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
            lac=cell.lac, cid=cell.cid + 1,
            time=now, count=1,
        )
        self.session.add(black)
        self.session.flush()

        result = insert_measures_cell.delay(observations)
        self.assertEqual(result.get(), 2)

        self.assertEqual(self.data_queue.size(), 2)
        update_cell.delay().get()

        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 2)

        self.check_statcounter(StatKey.cell, 2)
        self.check_statcounter(StatKey.unique_cell, 2)

    def test_blacklist_time_used_as_creation_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLACKLIST_DURATION - timedelta(days=1)

        cell = CellFactory.build()
        self.session.add(
            CellBlacklist(time=last_week, count=1,
                          radio=cell.radio, mcc=cell.mcc,
                          mnc=cell.mnc, lac=cell.lac, cid=cell.cid))
        self.session.flush()

        # add a new entry for the previously blacklisted cell
        obs = dict(lat=cell.lat, lon=cell.lon,
                   radio=int(cell.radio), mcc=cell.mcc, mnc=cell.mnc,
                   lac=cell.lac, cid=cell.cid)
        insert_measures_cell.delay([obs]).get()

        self.assertEqual(self.data_queue.size(), 1)
        update_cell.delay().get()

        # the cell was inserted again
        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 1)

        # and the creation date was set to the date of the blacklist entry
        self.assertEqual(cells[0].created, last_week)

        self.check_statcounter(StatKey.cell, 1)
        self.check_statcounter(StatKey.unique_cell, 0)

    def test_insert_observations(self):
        time = util.utcnow() - timedelta(days=1)

        cell = CellFactory(radio=Radio.gsm, total_measures=5)
        user = User(nickname=u'test')
        self.session.add(user)
        self.session.flush()

        obs = dict(
            radio=int(cell.radio), mcc=cell.mcc, mnc=cell.mnc,
            created=time, time=time, lat=cell.lat, lon=cell.lon,
            accuracy=0, altitude=0, altitude_accuracy=0,
        )
        entries = [
            # Note that this first entry will be skipped as it does
            # not include (lac, cid) or (psc)
            {'signal': -100},
            {'lac': cell.lac, 'cid': cell.cid, 'psc': cell.psc, 'asu': 8},
            {'lac': cell.lac, 'cid': cell.cid, 'psc': cell.psc, 'asu': 8},
            {'lac': cell.lac, 'cid': cell.cid, 'psc': cell.psc, 'asu': 15},
            {'lac': cell.lac, 'cid': cell.cid + 1, 'psc': cell.psc},
        ]
        for entry in entries:
            entry.update(obs)

        result = insert_measures_cell.delay(entries, userid=user.id)
        self.assertEqual(result.get(), 4)

        self.assertEqual(self.data_queue.size(), 4)
        update_cell.delay().get()

        self.session.refresh(cell)
        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 2)
        self._compare_sets([c.mcc for c in cells], [cell.mcc])
        self._compare_sets([c.mnc for c in cells], [cell.mnc])
        self._compare_sets([c.lac for c in cells], [cell.lac])
        self._compare_sets([c.cid for c in cells], [cell.cid, cell.cid + 1])
        self._compare_sets([c.psc for c in cells], [cell.psc])
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

    def test_insert_observations_invalid_lac(self):
        time = util.utcnow() - timedelta(days=1)
        today = util.utcnow().date()

        cell = CellFactory(total_measures=5)
        self.session.add(Score(key=ScoreKey.new_cell,
                               userid=1, time=today, value=7))
        self.session.flush()

        obs = dict(
            radio=int(cell.radio), mcc=cell.mcc, mnc=cell.mnc, psc=cell.psc,
            created=time, time=time, lat=cell.lat, lon=cell.lon,
            accuracy=0, altitude=0, altitude_accuracy=0)
        entries = [
            {'lac': constants.MAX_LAC_ALL + 1,
             'cid': constants.MAX_CID_ALL + 1, 'asu': 8},
            {'lac': None, 'cid': None, 'asu': 8},
        ]
        for entry in entries:
            entry.update(obs)

        result = insert_measures_cell.delay(entries, userid=1)
        self.assertEqual(result.get(), 0)

        # The incomplete observations never make it into the queue
        self.assertEqual(self.data_queue.size(), 0)
        update_cell.delay().get()

        # Nothing should change in the initially created Cell record
        self.session.refresh(cell)
        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        self._compare_sets([c.total_measures for c in cells], [5])

    def test_insert_observations_out_of_range(self):
        cell = CellFactory.build()

        obs = dict(
            lat=cell.lat, lon=cell.lon,
            radio=int(cell.radio), mcc=cell.mcc, mnc=cell.mnc,
            lac=cell.lac, cid=cell.cid)
        entries = [
            {'asu': 8, 'signal': -70, 'ta': 32},
            {'asu': -10, 'signal': -300, 'ta': -10},
            {'asu': 256, 'signal': 16, 'ta': 128},
        ]
        for entry in entries:
            entry.update(obs)

        result = insert_measures_cell.delay(entries)
        self.assertEqual(result.get(), 3)

        observations = self.data_queue.dequeue()
        self.assertEqual(len(observations), 3)
        self._compare_sets([o.asu for o in observations], [None, 8])
        self._compare_sets([o.signal for o in observations], [None, -70])
        self._compare_sets([o.ta for o in observations], [None, 32])


class TestWifi(ObservationTestCase):

    def setUp(self):
        super(TestWifi, self).setUp()
        self.data_queue = self.celery_app.data_queues['update_wifi']

    def test_blacklist(self):
        utcnow = util.utcnow()

        bad_wifi = WifiFactory.build()
        good_wifi = WifiFactory.build()
        black = WifiBlacklist(time=utcnow, count=1, key=bad_wifi.key)
        self.session.add(black)
        self.session.flush()

        obs = dict(lat=good_wifi.lat, lon=good_wifi.lon)
        entries = [
            {'key': good_wifi.key},
            {'key': good_wifi.key},
            {'key': bad_wifi.key},
        ]
        for entry in entries:
            entry.update(obs)

        result = insert_measures_wifi.delay(entries)
        self.assertEqual(result.get(), 2)

        self.assertEqual(self.data_queue.size(), 2)
        update_wifi.delay().get()

        wifis = self.session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)
        self._compare_sets([w.key for w in wifis], [good_wifi.key])

        self.check_statcounter(StatKey.wifi, 2)
        self.check_statcounter(StatKey.unique_wifi, 1)

    def test_blacklist_time_used_as_creation_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLACKLIST_DURATION - timedelta(days=1)

        wifi = WifiFactory.build()
        self.session.add(WifiBlacklist(time=last_week, count=1, key=wifi.key))
        self.session.flush()

        # add a new entry for the previously blacklisted wifi
        obs = dict(lat=wifi.lat, lon=wifi.lon, key=wifi.key)
        insert_measures_wifi.delay([obs]).get()

        self.assertEqual(self.data_queue.size(), 1)
        update_wifi.delay().get()

        # the wifi was inserted again
        wifis = self.session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)

        # and the creation date was set to the date of the blacklist entry
        self.assertEqual(wifis[0].created, last_week)
        self.check_statcounter(StatKey.unique_wifi, 0)

    def test_insert_observations(self):
        session = self.session
        time = util.utcnow() - timedelta(days=1)

        wifi = WifiFactory(total_measures=0)
        wifi2 = WifiFactory.build(total_measures=0)
        user = User(nickname=u'test')
        session.add(user)
        session.flush()

        obs = dict(
            created=time, time=time, lat=wifi.lat, lon=wifi.lon,
            accuracy=None, altitude=None, altitude_accuracy=None,
            heading=52.9, speed=158.5,
        )
        entries = [
            {'key': wifi.key, 'channel': 11, 'signal': -80},
            {'key': wifi.key, 'channel': 3, 'signal': -90},
            {'key': wifi.key, 'channel': 3, 'signal': -80},
            {'key': wifi2.key, 'channel': 3, 'signal': -90},
        ]
        for entry in entries:
            entry.update(obs)
        result = insert_measures_wifi.delay(entries, userid=user.id)
        self.assertEqual(result.get(), 4)

        self.assertEqual(self.data_queue.size(), 4)
        update_wifi.delay().get()

        self.session.refresh(wifi)
        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 2)
        self._compare_sets([w.key for w in wifis], [wifi.key, wifi2.key])
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


class TestSubmitV1Errors(ObservationTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_rw.engine)
        super(TestSubmitV1Errors, self).tearDown()

    def test_database_error(self):
        self.session.execute(text('drop table wifi;'))

        wifi = WifiFactory.build()
        wifi2 = WifiFactory.build()

        entries = [
            {'lat': wifi.lat, 'lon': wifi.lon, 'key': wifi.key, 'channel': 7},
            {'lat': wifi.lat, 'lon': wifi.lon, 'key': wifi.key, 'channel': 3},
            {'lat': wifi.lat, 'lon': wifi.lon, 'key': wifi.key, 'channel': 3},
            {'lat': wifi2.lat, 'lon': wifi2.lon, 'key': wifi2.key},
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
