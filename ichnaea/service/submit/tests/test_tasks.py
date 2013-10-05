from datetime import datetime

from ichnaea.content.models import (
    Score,
    SCORE_TYPE,
)
from ichnaea.models import (
    Cell,
    CellMeasure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.decimaljson import encode_datetime
from ichnaea.tests.base import CeleryTestCase


class TestInsert(CeleryTestCase):

    def test_cell(self):
        from ichnaea.service.submit.tasks import insert_cell_measure
        session = self.db_master_session
        utcnow = datetime.utcnow()

        session.add(Cell(radio=0, mcc=1, mnc=2, lac=3, cid=4,
                         new_measures=2, total_measures=5))
        session.add(Score(userid=1, key=SCORE_TYPE['new_cell'], value=7))
        session.flush()

        measure = dict(
            id=0, created=encode_datetime(utcnow), lat=10000000, lon=20000000,
            time=encode_datetime(utcnow), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=0,
        )
        entries = [
            {"mcc": 1, "mnc": 2, "signal": -100},
            {"mcc": 1, "mnc": 2, "lac": 3, "cid": 4, "psc": 5, "asu": 8},
            {"mcc": 1, "mnc": 2, "lac": 3, "cid": 4, "asu": 8},
            {"mcc": 1, "mnc": 2, "lac": 3, "cid": 4, "asu": 15},
            {"mcc": 1, "mnc": 2, "lac": 3, "cid": 7},
        ]
        result = insert_cell_measure.delay(measure, entries, userid=1)
        self.assertEqual(result.get(), 5)

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 5)
        self.assertEqual(set([m.mcc for m in measures]), set([1]))
        self.assertEqual(set([m.mnc for m in measures]), set([2]))
        self.assertEqual(set([m.asu for m in measures]), set([0, 8, 15]))
        self.assertEqual(set([m.psc for m in measures]), set([0, 5]))
        self.assertEqual(set([m.signal for m in measures]), set([0, -100]))

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 2)
        self.assertEqual(set([c.mcc for c in cells]), set([1]))
        self.assertEqual(set([c.mnc for c in cells]), set([2]))
        self.assertEqual(set([c.lac for c in cells]), set([3]))
        self.assertEqual(set([c.cid for c in cells]), set([4, 7]))
        self.assertEqual(set([c.new_measures for c in cells]), set([1, 5]))
        self.assertEqual(set([c.total_measures for c in cells]), set([1, 8]))

        scores = session.query(Score).all()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].key, SCORE_TYPE['new_cell'])
        self.assertEqual(scores[0].value, 10)

        # test duplicate execution
        result = insert_cell_measure.delay(measure, entries, userid=1)
        self.assertEqual(result.get(), 5)
        # TODO this task isn't idempotent yet
        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 10)

    def test_wifi(self):
        from ichnaea.service.submit.tasks import insert_wifi_measure
        session = self.db_master_session
        utcnow = datetime.utcnow()

        session.add(Wifi(key="ab12"))
        session.add(Score(userid=1, key=SCORE_TYPE['new_wifi'], value=7))
        session.flush()

        measure = dict(
            id=0, created=encode_datetime(utcnow), lat=10000000, lon=20000000,
            time=encode_datetime(utcnow), accuracy=0, altitude=0,
            altitude_accuracy=0, radio=-1,
        )
        entries = [
            {"key": "ab12", "channel": 11, "signal": -80},
            {"key": "ab12", "channel": 3, "signal": -90},
            {"key": "ab12", "channel": 3, "signal": -80},
            {"key": "cd34", "channel": 3, "signal": -90},
        ]
        result = insert_wifi_measure.delay(measure, entries, userid=1)
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
        self.assertEqual(scores[0].value, 9)

        # test duplicate execution
        result = insert_wifi_measure.delay(measure, entries, userid=1)
        self.assertEqual(result.get(), 4)
        # TODO this task isn't idempotent yet
        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 8)

        # test error case
        entries[0]['id'] = measures[0].id
        result = insert_wifi_measure.delay(measure, entries)
        self.assertEqual(result.get(), 0)

    def test_wifi_blacklist(self):
        from ichnaea.service.submit.tasks import insert_wifi_measure
        session = self.db_master_session
        bad_key = "ab1234567890"
        good_key = "cd1234567890"
        black = WifiBlacklist(key=bad_key)
        session.add(black)
        session.flush()
        measure = dict(id=0, lat=10000000, lon=20000000)
        entries = [{"key": good_key}, {"key": good_key}, {"key": bad_key}]

        result = insert_wifi_measure.delay(measure, entries)
        self.assertEqual(result.get(), 2)

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 2)
        self.assertEqual(set([m.key for m in measures]), set([good_key]))
