from datetime import timedelta

from pytz import UTC

from ichnaea.customjson import (
    decode_datetime,
    encode_datetime,
)
from ichnaea.data.validation import (
    normalized_cell_measure_dict,
    normalized_time,
    normalized_wifi_measure_dict,
)
from ichnaea.data.constants import WIFI_TEST_KEY
from ichnaea.tests.base import TestCase
from ichnaea.tests.base import (
    FREMONT_LAT, FREMONT_LON, USA_MCC,
    SAO_PAULO_LAT, SAO_PAULO_LON, BRAZIL_MCC,
    PARIS_LAT, PARIS_LON, FRANCE_MCC
)
from ichnaea import util


class TestValidation(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.time = util.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')

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

    def make_cell_submission(self, **kw):
        measure = dict(radio='umts',
                       lat=PARIS_LAT,
                       lon=PARIS_LON, accuracy=120,
                       altitude=220, altitude_accuracy=10,
                       time=self.time)
        cell = dict(mcc=FRANCE_MCC, mnc=220, lac=12345, cid=34567, psc=-1,
                    asu=15, signal=-83, ta=5)
        for (k, v) in kw.items():
            if k in measure:
                measure[k] = v
            else:
                cell[k] = v
        return (measure, cell)

    def make_wifi_submission(self, **kw):
        measure = dict(radio='',
                       lat=49.25,
                       lon=123.10, accuracy=120,
                       altitude=220, altitude_accuracy=10,
                       time=self.time)
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

        invalid_mccs = [-10, 0, 101, 1000, 3456]

        valid_mncs = [0, 542, 999]
        valid_cdma_mncs = [0, 542, 32767]
        invalid_mncs = [-10, -1, 32768, 93870]

        valid_lacs = [1, 763, 65535]
        invalid_lacs = [-1, 0, -10, 65536, 987347]

        valid_cids = [1, 12345, 268435455]
        invalid_cids = [-10, -1, 0, 268435456, 498169872]

        valid_pscs = [0, 120, 512]
        invalid_pscs = [-1, 513, 4456]

        valid_lat_lon_mcc_triples = [
            (FREMONT_LAT, FREMONT_LON, USA_MCC),
            (SAO_PAULO_LAT, SAO_PAULO_LON, BRAZIL_MCC),
            (PARIS_LAT, PARIS_LON, FRANCE_MCC)]

        invalid_latitudes = [-100.0, -85.0511, 85.0511, 100.0]
        invalid_longitudes = [-190.0, -180.1, 180.1, 190]

        valid_accuracies = [0, 1, 100, 10000]
        invalid_accuracies = [-10, -1, 5000000]

        valid_altitudes = [-100, -1, 0, 10, 100]
        invalid_altitudes = [-20000, 200000]

        valid_altitude_accuracies = [0, 1, 100, 1000]
        invalid_altitude_accuracies = [-10, -1, 500000]

        valid_asus = [0, 10, 31, 97]
        invalid_asus = [-10, -1, 99]

        valid_tas = [0, 15, 63]
        invalid_tas = [-10, -1, 64, 100]

        valid_signals = [-150, -100, -1]
        invalid_signals = [-300, -151, 0, 10]

        # Try all radio values
        for (radio, v) in radio_pairs:
            (measure, cell) = self.make_cell_submission(radio=radio)
            self.check_normalized_cell(measure, cell, dict(radio=v))

        # Try all valid (lat, lon, mcc, mnc) groups
        for (lat, lon, mcc) in valid_lat_lon_mcc_triples:
            for mnc in valid_mncs:
                (measure, cell) = self.make_cell_submission(
                    lat=lat, lon=lon, mcc=mcc, mnc=mnc)
                self.check_normalized_cell(measure, cell, dict(lat=lat,
                                                               lon=lon,
                                                               mcc=mcc,
                                                               mnc=mnc))
            for mnc in valid_cdma_mncs:
                (measure, cell) = self.make_cell_submission(
                    lat=lat, lon=lon, mcc=mcc, mnc=mnc, radio='cdma')
                self.check_normalized_cell(measure, cell, dict(lat=lat,
                                                               lon=lon,
                                                               mcc=mcc,
                                                               mnc=mnc))

        # Try outside of country lat/lon
        (measure, cell) = self.make_cell_submission(
            mcc=USA_MCC, lat=PARIS_LAT, lon=PARIS_LON)
        self.check_normalized_cell(measure, cell, None)

        # Try all invalid mcc variants individually
        for mcc in invalid_mccs:
            (measure, cell) = self.make_cell_submission(mcc=mcc)
            self.check_normalized_cell(measure, cell, None)

        # Try all invalid mnc variants individually
        for mnc in invalid_mncs:
            (measure, cell) = self.make_cell_submission(mnc=mnc)
            self.check_normalized_cell(measure, cell, None)

        # Try all valid (lac, cid) pairs, with invalid pscs
        for lac in valid_lacs:
            for cid in valid_cids:
                for psc in invalid_pscs:
                    (measure, cell) = self.make_cell_submission(
                        lac=lac, cid=cid, psc=psc)
                    self.check_normalized_cell(measure, cell, dict(lac=lac,
                                                                   cid=cid,
                                                                   psc=-1))

        # Try all invalid lacs, with an invalid psc
        for lac in invalid_lacs:
            for psc in invalid_pscs:
                (measure, cell) = self.make_cell_submission(lac=lac, psc=psc)
                self.check_normalized_cell(measure, cell, None)

        # Try all invalid cids, with an invalid psc
        for cid in invalid_cids:
            for psc in invalid_pscs:
                (measure, cell) = self.make_cell_submission(cid=cid, psc=psc)
                self.check_normalized_cell(measure, cell, None)

        # Try all invalid lacs, with a valid psc
        for lac in invalid_lacs:
            for psc in valid_pscs:
                (measure, cell) = self.make_cell_submission(lac=lac, psc=psc)
                self.check_normalized_cell(measure, cell, dict(lac=-1,
                                                               psc=psc))

        # Try all invalid cids, with a valid psc
        for cid in invalid_cids:
            for psc in valid_pscs:
                (measure, cell) = self.make_cell_submission(cid=cid, psc=psc)
                self.check_normalized_cell(measure, cell, dict(cid=-1,
                                                               psc=psc))

        # Try special invalid lac, cid 65535 combination
        (measure, cell) = self.make_cell_submission(lac=0, cid=65535)
        self.check_normalized_cell(measure, cell, None)

        # Try all invalid latitudes individually
        for lat in invalid_latitudes:
            (measure, cell) = self.make_cell_submission(lat=lat)
            self.check_normalized_cell(measure, cell, None)

        # Try all invalid longitudes individually
        for lon in invalid_longitudes:
            (measure, cell) = self.make_cell_submission(lon=lon)
            self.check_normalized_cell(measure, cell, None)

        # Try all 'nice to have' valid fields individually
        for (k, vs) in [('accuracy', valid_accuracies),
                        ('altitude', valid_altitudes),
                        ('altitude_accuracy', valid_altitude_accuracies),
                        ('asu', valid_asus),
                        ('ta', valid_tas),
                        ('signal', valid_signals)]:
            for v in vs:
                (measure, cell) = self.make_cell_submission(**{k: v})
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
                (measure, cell) = self.make_cell_submission(**{k: v})
                self.check_normalized_cell(measure, cell, {k: x})

        # Try asu/signal field mix-up
        (measure, cell) = self.make_cell_submission(asu=-75, signal=0)
        self.check_normalized_cell(measure, cell, {'signal': -75})

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
            ("f1234abcd345", "f1234abcd345"),
            # We considered but do not ban locally administered wifi keys
            # based on the U/L bit https://en.wikipedia.org/wiki/MAC_address
            ("0a:00:00:00:00:00", "0a0000000000"),
        ]
        invalid_keys = [
            "ab:cd",
            "ffffffffffff",
            "000000000000",
            "00000000001",
            "00000000000g",
            "12#34:56:78:90:12",
            "[1234.56.78.9012]",
        ] + [WIFI_TEST_KEY] + [
            c.join([str.format("{x:02x}", x=x)
                    for x in range(6)])
            for c in "!@#$%^&*()_+={}\x01\x02\x03\r\n"]

        valid_signals = [-200, -100, -1]
        invalid_signals = [-300, -201, 0, 10]

        valid_snrs = [0, 12, 100]
        invalid_snrs = [-1, -50, 101]

        # Check valid keys
        for (k1, k2) in valid_key_pairs:
            (measure, wifi) = self.make_wifi_submission(key=k1)
            self.check_normalized_wifi(measure, wifi, dict(key=k2))

        # Check invalid keys
        for k in invalid_keys:
            (measure, wifi) = self.make_wifi_submission(key=k)
            self.check_normalized_wifi(measure, wifi, None)

        # Check valid frequency/channel pairs together and
        # individually.
        for (f, c) in valid_frequency_channels:
            (measure, wifi) = self.make_wifi_submission(
                frequency=f, channel=c)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

            (measure, wifi) = self.make_wifi_submission(
                frequency=f, channel=0)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

            (measure, wifi) = self.make_wifi_submission(
                frequency=0, channel=c)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

        # Check valid signals
        for s in valid_signals:
            (measure, wifi) = self.make_wifi_submission(signal=s)
            self.check_normalized_wifi(measure, wifi, dict(signal=s))

        # Check invalid signals
        for s in invalid_signals:
            (measure, wifi) = self.make_wifi_submission(signal=s)
            self.check_normalized_wifi(measure, wifi, dict(signal=0))

        # Check valid snrs
        for s in valid_snrs:
            (measure, wifi) = self.make_wifi_submission(signalToNoiseRatio=s)
            self.check_normalized_wifi(
                measure, wifi, dict(signalToNoiseRatio=s))

        # Check invalid snrs
        for s in invalid_snrs:
            (measure, wifi) = self.make_wifi_submission(signalToNoiseRatio=s)
            self.check_normalized_wifi(
                measure, wifi, dict(signalToNoiseRatio=0))

        # Check valid channels
        for c in valid_channels:
            (measure, wifi) = self.make_wifi_submission(channel=c)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

        # Check invalid channels are corrected by valid frequency
        for c in invalid_channels:
            (measure, wifi) = self.make_wifi_submission()
            chan = wifi['channel']
            wifi['channel'] = c
            wifi = self.check_normalized_wifi(measure, wifi,
                                              dict(channel=chan))
            self.assertFalse('frequency' in wifi)

        # Check invalid frequencies have no effect and are
        # dropped anyways
        for f in invalid_frequencies:
            (measure, wifi) = self.make_wifi_submission(frequency=f)
            chan = wifi['channel']
            wifi = self.check_normalized_wifi(measure, wifi,
                                              dict(channel=chan))
            self.assertFalse('frequency' in wifi)

    def test_normalize_time(self):
        now = util.utcnow()
        first_args = dict(day=1, hour=0, minute=0, second=0,
                          microsecond=0, tzinfo=UTC)
        now_enc = now.replace(**first_args)
        two_weeks_ago = now - timedelta(14)
        short_format = now.date().isoformat()

        entries = [
            ('', now_enc),
            (now, now_enc),
            (two_weeks_ago, two_weeks_ago.replace(**first_args)),
            (short_format, now_enc),
            ("2011-01-01T11:12:13.456Z", now_enc),
            ("2070-01-01T11:12:13.456Z", now_enc),
            ("10-10-10", now_enc),
            ("2011-10-13T.Z", now_enc),
        ]

        for entry in entries:
            in_, expected = entry
            if not isinstance(in_, str):
                in_ = encode_datetime(in_)
            self.assertEqual(
                decode_datetime(normalized_time(in_)), expected)

    def test_unhelpful_incomplete_cdma_cells(self):
        # CDMA cell records must have MNC, MCC, LAC and CID filled in
        entries = [
            # (data-in, data-out)
            ({'lac': 3, 'cid': 4}, {'lac': 3, 'cid': 4}),
            ({'lac': 3, 'cid': -1}, None),
            ({'lac': -1, 'cid': 4}, None),
            ({'lac': -1, 'cid': -1, 'psc': 5}, None),
        ]

        for entry in entries:
            (measure, cell) = self.make_cell_submission(
                radio='cdma', **entry[0])
            self.check_normalized_cell(measure, cell, entry[1])

    def test_unhelpful_incomplete_cells(self):
        entries = [
            # These records fail the mcc check
            {"mcc": 0, "mnc": 2, "lac": 3, "cid": 4},
            {"mcc": -1, "mnc": 2, "lac": 3, "cid": 4},
            {"mcc": -2, "mnc": 2, "lac": 3, "cid": 4},
            {"mcc": 2000, "mnc": 2, "lac": 3, "cid": 4},

            # These records fail the mnc check
            {"mcc": FRANCE_MCC, "mnc": -1, "lac": 3, "cid": 4},
            {"mcc": FRANCE_MCC, "mnc": -2, "lac": 3, "cid": 4},
            {"mcc": FRANCE_MCC, "mnc": 33000, "lac": 3, "cid": 4},

            # These records fail the lac check
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": -1, "cid": 4},
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": -2, "cid": 4},
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": 65536, "cid": 4},

            # These records fail the cid check
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": 3, "cid": -1},
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": 3, "cid": -2},
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": 3, "cid": 2 ** 28},

            # These records fail the (lac or cid) and psc check
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": -1, "cid": -1},
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": 3, "cid": -1},
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": -1, "cid": 4},

            # This fails the check for (unknown lac, cid=65535)
            # and subsequently the check for missing psc
            {"mcc": FRANCE_MCC, "mnc": 2, "lac": 0, "cid": 65535, "psc": -1},

            # This fails because it has an MNC above 1000 for a GSM network
            {"mcc": FRANCE_MCC, "mnc": 1001, "lac": 3, "cid": 4,
             "radio": "gsm"},
        ]

        for entry in entries:
            if 'radio' not in entry:
                entry['radio'] = 'cdma'
            (measure, cell) = self.make_cell_submission(**entry)
            self.check_normalized_cell(measure, cell, None)

    def test_wrong_radio_type_is_corrected_for_large_cid(self):
        measure, cell = self.make_cell_submission(cid=65536, radio="gsm")
        self.check_normalized_cell(measure, cell, {'radio': 2})
