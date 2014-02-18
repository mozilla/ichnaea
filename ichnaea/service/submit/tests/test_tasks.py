from datetime import (
    datetime,
    timedelta,
)

from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text

from ichnaea.content.models import (
    Score,
    SCORE_TYPE,
)
from ichnaea.heka_logging import RAVEN_ERROR
from ichnaea.models import (
    Cell,
    CellMeasure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.decimaljson import (
    encode_datetime,
)
from ichnaea.tests.base import CeleryTestCase


class TestInsert(CeleryTestCase):

    def test_cell(self):
        from ichnaea.service.submit.tasks import insert_cell_measure
        session = self.db_master_session
        time = datetime.utcnow().replace(microsecond=0) - timedelta(days=1)

        session.add(Cell(radio=0, mcc=1, mnc=2, lac=3, cid=4, psc=5,
                         new_measures=2, total_measures=5))
        session.add(Score(userid=1, key=SCORE_TYPE['new_cell'], value=7))
        session.flush()

        measure = dict(
            id=0, created=encode_datetime(time), lat=10000000, lon=20000000,
            time=encode_datetime(time), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=0,
        )
        entries = [
            {"mcc": 1, "mnc": 2, "signal": -100},
            {"mcc": 1, "mnc": 2, "lac": 3, "cid": 4, "psc": 5, "asu": 8},
            {"mcc": 1, "mnc": 2, "lac": 3, "cid": 4, "psc": 5, "asu": 8},
            {"mcc": 1, "mnc": 2, "lac": 3, "cid": 4, "psc": 5, "asu": 15},
            {"mcc": 1, "mnc": 2, "lac": 3, "cid": 7, "psc": 5},
        ]
        result = insert_cell_measure.delay(measure, entries, userid=1)
        self.assertEqual(result.get(), 5)

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 5)
        self.assertEqual(set([m.mcc for m in measures]), set([1]))
        self.assertEqual(set([m.mnc for m in measures]), set([2]))
        self.assertEqual(set([m.asu for m in measures]), set([-1, 8, 15]))
        self.assertEqual(set([m.psc for m in measures]), set([-1, 5]))
        self.assertEqual(set([m.signal for m in measures]), set([0, -100]))

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 2)
        self.assertEqual(set([c.mcc for c in cells]), set([1]))
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
        result = insert_cell_measure.delay(measure, entries, userid=1)
        self.assertEqual(result.get(), 5)
        # TODO this task isn't idempotent yet
        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 10)

    def test_insert_invalid_lac(self):
        from ichnaea.service.submit.tasks import insert_cell_measure
        session = self.db_master_session
        time = datetime.utcnow().replace(microsecond=0) - timedelta(days=1)

        session.add(Cell(radio=0, mcc=1, mnc=2, lac=3, cid=4,
                         new_measures=2, total_measures=5))
        session.add(Score(userid=1, key=SCORE_TYPE['new_cell'], value=7))
        session.flush()

        measure = dict(
            id=0, created=encode_datetime(time), lat=10000000, lon=20000000,
            time=encode_datetime(time), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=0,
        )
        entries = [
            {"mcc": 1, "mnc": 2, "lac": 3147483647, "cid": 2147483647,
             "psc": 5, "asu": 8},
            {"mcc": 1, "mnc": 2, "lac": -1, "cid": -1,
             "psc": 5, "asu": 8},
        ]
        result = insert_cell_measure.delay(measure, entries, userid=1)
        self.assertEqual(result.get(), 2)

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 2)
        self.assertEqual(set([m.lac for m in measures]), set([-1]))
        self.assertEqual(set([m.cid for m in measures]), set([-1]))

        # Nothing should change in the initially created Cell record
        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        self.assertEqual(set([c.new_measures for c in cells]), set([2]))
        self.assertEqual(set([c.total_measures for c in cells]), set([5]))

    def test_cell_out_of_range_values(self):
        from ichnaea.service.submit.tasks import insert_cell_measure
        session = self.db_master_session
        time = datetime.utcnow().replace(microsecond=0) - timedelta(days=1)

        measure = dict(
            id=0, created=encode_datetime(time), lat=10000000, lon=20000000,
            time=encode_datetime(time), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=0, mcc=1, mnc=2, lac=3, cid=4,
        )
        entries = [
            {"asu": 8, "signal": -70, "ta": 32},
            {"asu": -10, "signal": -300, "ta": -10},
            {"asu": 256, "signal": 16, "ta": 128},
        ]
        result = insert_cell_measure.delay(measure, entries)
        self.assertEqual(result.get(), 3)

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 3)
        self.assertEqual(set([m.asu for m in measures]), set([-1, 8]))
        self.assertEqual(set([m.signal for m in measures]), set([0, -70]))
        self.assertEqual(set([m.ta for m in measures]), set([0, 32]))

    def test_wifi(self):
        from ichnaea.service.submit.tasks import insert_wifi_measures
        session = self.db_master_session
        time = datetime.utcnow().replace(microsecond=0) - timedelta(days=1)

        session.add(Wifi(key="ab12"))
        session.add(Score(userid=1, key=SCORE_TYPE['new_wifi'], value=7))
        session.flush()

        measure = dict(
            id=0, created=encode_datetime(time), lat=10000000, lon=20000000,
            time=encode_datetime(time), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=-1,
        )
        entries = [
            {"key": "ab12", "channel": 11, "signal": -80},
            {"key": "ab12", "channel": 3, "signal": -90},
            {"key": "ab12", "channel": 3, "signal": -80},
            {"key": "cd34", "channel": 3, "signal": -90},
        ]
        for e in entries:
            e.update(measure)
        result = insert_wifi_measures.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 4)
        self.assertEqual(set([m.key for m in measures]), set(["ab12", "cd34"]))
        self.assertEqual(set([m.channel for m in measures]), set([3, 11]))
        self.assertEqual(set([m.signal for m in measures]), set([-80, -90]))

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 2)
        self.assertEqual(set([w.key for w in wifis]), set(["ab12", "cd34"]))
        self.assertEqual(set([w.new_measures for w in wifis]), set([1, 3]))
        self.assertEqual(set([w.total_measures for w in wifis]), set([1, 3]))

        scores = session.query(Score).all()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].key, SCORE_TYPE['new_wifi'])
        self.assertEqual(scores[0].value, 8)

        # test duplicate execution
        result = insert_wifi_measures.delay(entries, userid=1)
        self.assertEqual(result.get(), 4)
        # TODO this task isn't idempotent yet
        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 8)

    def test_wifi_blacklist(self):
        from ichnaea.service.submit.tasks import insert_wifi_measures
        session = self.db_master_session
        bad_key = "ab1234567890"
        good_key = "cd1234567890"
        black = WifiBlacklist(key=bad_key)
        session.add(black)
        session.flush()
        measure = dict(id=0, lat=10000000, lon=20000000)
        entries = [{"key": good_key}, {"key": good_key}, {"key": bad_key}]
        for e in entries:
            e.update(measure)

        result = insert_wifi_measures.delay(entries)
        self.assertEqual(result.get(), 3)

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 3)
        self.assertEqual(
            set([m.key for m in measures]), set([bad_key, good_key]))

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)
        self.assertEqual(set([w.key for w in wifis]), set([good_key]))


class TestSubmitErrors(CeleryTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def test_database_error(self):
        from ichnaea.service.submit.tasks import insert_wifi_measures
        session = self.db_master_session

        stmt = text("drop table wifi;")
        session.execute(stmt)

        entries = [
            {"lat": 10000000, "lon": 20000000, "key": "ab12", "channel": 11},
            {"lat": 10000000, "lon": 20000000, "key": "ab12", "channel": 3},
            {"lat": 10000000, "lon": 20000000, "key": "ab12", "channel": 3},
            {"lat": 10000000, "lon": 20000000, "key": "cd34", "channel": 3},
        ]

        try:
            insert_wifi_measures.delay(entries)
        except ProgrammingError:
            pass
        except Exception as exc:
            self.fail("Unexpected exception caught: %s" % repr(exc))

        find_msg = self.find_heka_messages
        self.assertEquals(
            len(find_msg('sentry', RAVEN_ERROR, field_name='msg')), 1)
