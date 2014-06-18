import datetime

from sqlalchemy.exc import IntegrityError

from ichnaea.tests.base import DBTestCase
from ichnaea.models import (
    from_degrees,
    normalized_cell_measure_dict,
    normalized_wifi_measure_dict,
)
from ichnaea.tests.base import (
    FREMONT_LAT, FREMONT_LON, USA_MCC,
    SAO_PAULO_LAT, SAO_PAULO_LON, BRAZIL_MCC,
    PARIS_LAT, PARIS_LON, FRANCE_MCC
)

from unittest2 import TestCase


class TestCell(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import Cell
        return Cell(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertTrue(cell.id is None)
        self.assertEqual(cell.new_measures, 0)
        self.assertEqual(cell.total_measures, 0)

    def test_fields(self):
        cell = self._make_one(
            lat=12345678, lon=23456789, mcc=100, mnc=5, lac=12345, cid=234567,
            new_measures=2, total_measures=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.cid, 234567)
        self.assertEqual(result.new_measures, 2)
        self.assertEqual(result.total_measures, 15)


class TestCellMeasure(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import CellMeasure
        return CellMeasure(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertTrue(cell.id is None)

    def test_fields(self):
        cell = self._make_one(lat=12345678, lon=23456789, radio=0, mcc=100,
                              mnc=5, lac=12345, cid=234567, asu=26,
                              signal=-61, ta=10)
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.measure_id, 0)
        self.assertTrue(isinstance(result.created, datetime.datetime))
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.radio, 0)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 12345)
        self.assertEqual(result.cid, 234567)
        self.assertEqual(result.asu, 26)
        self.assertEqual(result.signal, -61)
        self.assertEqual(result.ta, 10)


class TestWifi(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import Wifi
        return Wifi(**kw)

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.key is None)
        self.assertEqual(wifi.new_measures, 0)
        self.assertEqual(wifi.total_measures, 0)

    def test_fields(self):
        key = "3680873e9b83"
        wifi = self._make_one(
            key=key, lat=12345678, lon=23456789, range=200,
            new_measures=2, total_measures=15,
        )
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.range, 200)
        self.assertEqual(result.new_measures, 2)
        self.assertEqual(result.total_measures, 15)


class TestWifiBlacklist(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import WifiBlacklist
        return WifiBlacklist(**kw)

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.key is None)
        self.assertTrue(wifi.created is not None)

    def test_fields(self):
        key = "3680873e9b83"
        wifi = self._make_one(key=key)
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertTrue(isinstance(result.created, datetime.datetime))

    def test_unique_key(self):
        key = "3680873e9b83"
        wifi1 = self._make_one(key=key)
        session = self.db_master_session
        session.add(wifi1)
        session.commit()

        wifi2 = self._make_one(key=key)
        session.add(wifi2)
        self.assertRaises(IntegrityError, session.commit)


class TestWifiMeasure(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import WifiMeasure
        return WifiMeasure(**kw)

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.id is None)

    def test_fields(self):
        key = "3680873e9b83"
        wifi = self._make_one(
            lat=12345678, lon=23456789, key=key, channel=2412, signal=-45)
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.measure_id, 0)
        self.assertTrue(isinstance(result.created, datetime.datetime))
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.key, key)
        self.assertEqual(result.channel, 2412)
        self.assertEqual(result.signal, -45)


class TestMeasure(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import Measure
        return Measure(**kw)

    def test_constructor(self):
        measure = self._make_one()
        self.assertTrue(measure.id is None)

    def test_fields(self):
        measure = self._make_one()
        session = self.db_master_session
        session.add(measure)
        session.commit()

        result = session.query(measure.__class__).first()
        self.assertFalse(result.id is None)


class TestNormalization(TestCase):

    def check_normalized_cell(self, measure, cell, expect):
        d = measure.copy()
        d.update(cell)
        result = normalized_cell_measure_dict(d)

        if expect is None:
            self.assertEqual(result, expect)
        else:
            for (k, v) in expect.items():
                self.assertEqual(result[k], v)
        return result

    def test_normalize_cells(self):

        radio_pairs = [('gsm', 0),
                       ('cdma', 1),
                       ('umts', 2),
                       ('wcdma', 2),
                       ('lte', 3),
                       ('wimax', -1),
                       ('', -1),
                       ('hspa', -1),
                       ('n/a', -1)]

        invalid_mccs = [-10, 0, 1000, 3456]

        valid_mncs = [0, 542, 32767]
        invalid_mncs = [-10, -1, 32768, 93870]

        valid_lacs = [0, 763, 65535]
        invalid_lacs = [-1, -10, 65536, 987347]

        valid_cids = [0, 12345, 268435455]
        invalid_cids = [-10, -1, 268435456, 498169872]

        valid_pscs = [0, 120, 512]
        invalid_pscs = [-1, 513, 4456]

        valid_lat_lon_mcc_triples = [
            (from_degrees(lat), from_degrees(lon), mcc)
            for (lat, lon, mcc) in
            [(FREMONT_LAT, FREMONT_LON, USA_MCC),
             (SAO_PAULO_LAT, SAO_PAULO_LON, BRAZIL_MCC),
             (PARIS_LAT, PARIS_LON, FRANCE_MCC)]]

        invalid_latitudes = [from_degrees(x)
                             for x in [-100.0, -90.1, 90.1, 100.0]]

        invalid_longitudes = [from_degrees(x)
                              for x in [-190.0, -180.1, 180.1, 190]]

        valid_accuracies = [0, 1, 100, 10000]
        invalid_accuracies = [-10, -1, 5000000]

        valid_altitudes = [-100, -1, 0, 10, 100]
        invalid_altitudes = [-20000, 200000]

        valid_altitude_accuracies = [0, 1, 100, 1000]
        invalid_altitude_accuracies = [-10, -1, 500000]

        valid_asus = [0, 10, 31]
        invalid_asus = [-10, -1, 32, 100]

        valid_tas = [0, 15, 63]
        invalid_tas = [-10, -1, 64, 100]

        valid_signals = [-200, -100, -1]
        invalid_signals = [-300, -201, 0, 10]

        time = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')

        def make_submission(**kw):
            measure = dict(radio='umts',
                           lat=from_degrees(PARIS_LAT),
                           lon=from_degrees(PARIS_LON), accuracy=120,
                           altitude=220, altitude_accuracy=10,
                           time=time)
            cell = dict(mcc=FRANCE_MCC, mnc=220, lac=12345, cid=34567, psc=-1,
                        asu=15, signal=-83, ta=5)
            for (k, v) in kw.items():
                if k in measure:
                    measure[k] = v
                else:
                    cell[k] = v
            return (measure, cell)

        # Try all radio values
        for (radio, v) in radio_pairs:
            (measure, cell) = make_submission(radio=radio)
            self.check_normalized_cell(measure, cell, dict(radio=v))

        # Try all valid (lat, lon, mcc, mnc) groups
        for (lat, lon, mcc) in valid_lat_lon_mcc_triples:
            for mnc in valid_mncs:
                (measure, cell) = make_submission(lat=lat, lon=lon,
                                                  mcc=mcc, mnc=mnc)
                self.check_normalized_cell(measure, cell, dict(lat=lat,
                                                               lon=lon,
                                                               mcc=mcc,
                                                               mnc=mnc))

        # Try all invalid mcc variants individually
        for mcc in invalid_mccs:
            (measure, cell) = make_submission(mcc=mcc)
            self.check_normalized_cell(measure, cell, None)

        # Try all invalid mnc variants individually
        for mnc in invalid_mncs:
            (measure, cell) = make_submission(mnc=mnc)
            self.check_normalized_cell(measure, cell, None)

        # Try all valid (lac, cid) pairs, with invalid pscs
        for lac in valid_lacs:
            for cid in valid_cids:
                for psc in invalid_pscs:
                    (measure, cell) = make_submission(lac=lac, cid=cid,
                                                      psc=psc)
                    self.check_normalized_cell(measure, cell, dict(lac=lac,
                                                                   cid=cid,
                                                                   psc=-1))

        # Try all invalid lacs, with an invalid psc
        for lac in invalid_lacs:
            for psc in invalid_pscs:
                (measure, cell) = make_submission(lac=lac, psc=psc)
                self.check_normalized_cell(measure, cell, None)

        # Try all invalid cids, with an invalid psc
        for cid in invalid_cids:
            for psc in invalid_pscs:
                (measure, cell) = make_submission(cid=cid, psc=psc)
                self.check_normalized_cell(measure, cell, None)

        # Try all invalid lacs, with a valid psc
        for lac in invalid_lacs:
            for psc in valid_pscs:
                (measure, cell) = make_submission(lac=lac, psc=psc)
                self.check_normalized_cell(measure, cell, dict(lac=-1,
                                                               psc=psc))

        # Try all invalid cids, with a valid psc
        for cid in invalid_cids:
            for psc in valid_pscs:
                (measure, cell) = make_submission(cid=cid, psc=psc)
                self.check_normalized_cell(measure, cell, dict(cid=-1,
                                                               psc=psc))

        # Try all invalid latitudes individually
        for lat in invalid_latitudes:
            (measure, cell) = make_submission(lat=lat)
            self.check_normalized_cell(measure, cell, None)

        # Try all invalid longitudes individually
        for lon in invalid_longitudes:
            (measure, cell) = make_submission(lon=lon)
            self.check_normalized_cell(measure, cell, None)

        # Try all 'nice to have' valid fields individually
        for (k, vs) in [('accuracy', valid_accuracies),
                        ('altitude', valid_altitudes),
                        ('altitude_accuracy', valid_altitude_accuracies),
                        ('asu', valid_asus),
                        ('ta', valid_tas),
                        ('signal', valid_signals)]:
            for v in vs:
                (measure, cell) = make_submission(**{k: v})
                self.check_normalized_cell(measure, cell, {k: v})

        # Try all 'nice to have' invalid fields individually
        for (k, vs, x) in [('accuracy', invalid_accuracies, 0),
                           ('altitude', invalid_altitudes, 0),
                           ('altitude_accuracy',
                            invalid_altitude_accuracies, 0),
                           ('asu', invalid_asus, -1),
                           ('ta', invalid_tas, 0),
                           ('signal', invalid_signals, 0)]:
            for v in vs:
                (measure, cell) = make_submission(**{k: v})
                self.check_normalized_cell(measure, cell, {k: x})

    def check_normalized_wifi(self, measure, wifi, expect):
        d = measure.copy()
        d.update(wifi)
        result = normalized_wifi_measure_dict(d)

        if expect is None:
            self.assertEqual(result, expect)
        else:
            for (k, v) in expect.items():
                self.assertEqual(result[k], v)
        return result

    def test_normalize_wifis(self):

        valid_channels = [1, 20, 45, 165]
        invalid_channels = [-10, -1, 201, 2500]

        valid_frequency_channels = [
            (2412, 1),
            (2427, 4),
            (2472, 13),
            (5170, 34),
            (5200, 40),
            (5805, 161),
            (5825, 165)
        ]
        invalid_frequencies = [-1, 2000, 2411, 2473,
                               5168, 5826, 6000]

        valid_key_pairs = [
            ("12:34:56:78:90:12", "123456789012"),
            ("12.34.56.78.90.12", "123456789012"),
            ("1234::5678::9012", "123456789012"),
            ("a2:b4:c6:d8:e0:f2", "a2b4c6d8e0f2"),
            ("A2:B4:C6:D8:E0:F2", "a2b4c6d8e0f2"),
            ("1-a3-b5-c7-D9-E1-F", "1a3b5c7d9e1f"),
            ("fffffffffff0", "fffffffffff0"),
            ("f00000000000", "f00000000000"),
            ("000000-a00000", "000000a00000"),
            ("f1234abcd345", "f1234abcd345")
        ]
        invalid_keys = [
            "ffffffffffff",
            "000000000000",
            "00000000001",
            "00000000000g",
            "12#34:56:78:90:12",
            "[1234.56.78.9012]",
        ] + [c.join([str.format("{x:02x}", x=x)
                     for x in range(6)])
             for c in "!@#$%^&*()_+={}\x01\x02\x03\r\n"]

        valid_signals = [-200, -100, -1]
        invalid_signals = [-300, -201, 0, 10]

        valid_snrs = [0, 12, 100]
        invalid_snrs = [-1, -50, 101]

        time = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')

        def make_submission(**kw):
            measure = dict(radio='',
                           lat=from_degrees(49.25),
                           lon=from_degrees(123.10), accuracy=120,
                           altitude=220, altitude_accuracy=10,
                           time=time)
            wifi = dict(key="12:34:56:78:90:12",
                        frequency=2442,
                        channel=7,
                        signal=-85,
                        signalToNoiseRatio=37)
            for (k, v) in kw.items():
                if k in measure:
                    measure[k] = v
                else:
                    wifi[k] = v
            return (measure, wifi)

        # Check valid keys
        for (k1, k2) in valid_key_pairs:
            (measure, wifi) = make_submission(key=k1)
            self.check_normalized_wifi(measure, wifi, dict(key=k2))

        # Check invalid keys
        for k in invalid_keys:
            (measure, wifi) = make_submission(key=k)
            self.check_normalized_wifi(measure, wifi, None)

        # Check valid frequency/channel pairs together and
        # individually.
        for (f, c) in valid_frequency_channels:
            (measure, wifi) = make_submission(frequency=f,
                                              channel=c)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

            (measure, wifi) = make_submission(frequency=f,
                                              channel=0)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

            (measure, wifi) = make_submission(frequency=0,
                                              channel=c)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

        # Check valid signals
        for s in valid_signals:
            (measure, wifi) = make_submission(signal=s)
            self.check_normalized_wifi(measure, wifi, dict(signal=s))

        # Check invalid signals
        for s in invalid_signals:
            (measure, wifi) = make_submission(signal=s)
            self.check_normalized_wifi(measure, wifi, dict(signal=0))

        # Check valid snrs
        for s in valid_snrs:
            (measure, wifi) = make_submission(signalToNoiseRatio=s)
            self.check_normalized_wifi(
                measure, wifi, dict(signalToNoiseRatio=s))

        # Check invalid snrs
        for s in invalid_snrs:
            (measure, wifi) = make_submission(signalToNoiseRatio=s)
            self.check_normalized_wifi(
                measure, wifi, dict(signalToNoiseRatio=0))

        # Check valid channels
        for c in valid_channels:
            (measure, wifi) = make_submission(channel=c)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

        # Check invalid channels are corrected by valid frequency
        for c in invalid_channels:
            (measure, wifi) = make_submission()
            chan = wifi['channel']
            wifi['channel'] = c
            wifi = self.check_normalized_wifi(measure, wifi,
                                              dict(channel=chan))
            self.assertFalse('frequency' in wifi)

        # Check invalid frequencies have no effect and are
        # dropped anyways
        for f in invalid_frequencies:
            (measure, wifi) = make_submission(frequency=f)
            chan = wifi['channel']
            wifi = self.check_normalized_wifi(measure, wifi,
                                              dict(channel=chan))
            self.assertFalse('frequency' in wifi)
