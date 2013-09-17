from datetime import datetime

from ichnaea.db import (
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.decimaljson import encode_datetime
from ichnaea.tests.base import CeleryTestCase


class TestInsert(CeleryTestCase):

    def test_wifi(self):
        from ichnaea.service.submit.tasks import insert_wifi_measure
        session = self.db_master_session
        utcnow = datetime.utcnow()

        session.add(Wifi(key="ab12"))
        session.flush()

        measure = dict(
            id=0, created=encode_datetime(utcnow), lat=10000000, lon=20000000,
            time=encode_datetime(utcnow), accuracy=0, altitude=0,
            altitude_accuracy=0,
        )
        entries = [
            {"key": "ab12", "channel": 11, "signal": -80},
            {"key": "cd34", "channel": 3, "signal": -90},
        ]
        result = insert_wifi_measure.delay(measure, entries)
        self.assertEqual(result.get(), 2)

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 2)
        self.assertEqual(set([m.key for m in measures]), set(["ab12", "cd34"]))
        self.assertEqual(set([m.channel for m in measures]), set([3, 11]))
        self.assertEqual(set([m.signal for m in measures]), set([-80, -90]))

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 2)
        self.assertEqual(set([w.key for w in wifis]), set(["ab12", "cd34"]))
        for wifi in wifis:
            self.assertEqual(wifi.new_measures, 1)
            self.assertEqual(wifi.total_measures, 1)

        # test duplicate execution
        result = insert_wifi_measure.delay(measure, entries)
        self.assertEqual(result.get(), 2)
        # TODO this task isn't idempotent yet
        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 4)

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
