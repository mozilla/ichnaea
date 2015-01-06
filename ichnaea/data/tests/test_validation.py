from datetime import timedelta

from pytz import UTC

from ichnaea.customjson import (
    decode_datetime,
    encode_datetime,
)
from ichnaea.data.validation import (
    normalized_cell_measure_dict,
    normalized_wifi_dict,
)
from ichnaea.data.schema import normalized_time
from ichnaea.data.constants import WIFI_TEST_KEY
from ichnaea.tests.base import TestCase
from ichnaea.tests.base import (
    FREMONT_LAT, FREMONT_LON, USA_MCC,
    SAO_PAULO_LAT, SAO_PAULO_LON, BRAZIL_MCC,
    PARIS_LAT, PARIS_LON, FRANCE_MCC
)
from ichnaea import util


class ValidationTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.time = util.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')


class TestCellValidation(ValidationTest):

    def check_normalized_cell(self, measure, cell, expect):
        d = measure.copy()
        d.update(cell)
        result = normalized_cell_measure_dict(d)

        if expect is None:
            self.assertEqual(result, expect)
        else:
            for (k, v) in expect.items():
                self.assertEqual(
                    result[k],
                    v,
                    '{key} in result should be {expected} not {actual}'.format(
                        key=k,
                        expected=v,
                        actual=result[k]))
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

    def setUp(self):
        self.radio_pairs = [
            ('gsm', 0),
            ('cdma', 1),
            ('umts', 2),
            ('wcdma', 2),
            ('lte', 3),
            ('wimax', -1),
            ('', -1),
            ('hspa', -1),
            ('n/a', -1),
        ]

        self.invalid_mccs = [-10, 0, 101, 1000, 3456]

        self.valid_mncs = [0, 542, 999]
        self.valid_cdma_mncs = [0, 542, 32767]
        self.invalid_mncs = [-10, -1, 32768, 93870]

        self.valid_lacs = [1, 763, 65535]
        self.invalid_lacs = [-1, 0, -10, 65536, 987347]

        self.valid_cids = [1, 12345, 268435455]
        self.invalid_cids = [-10, -1, 0, 268435456, 498169872]

        self.valid_pscs = [0, 120, 512]
        self.invalid_pscs = [-1, 513, 4456]

        self.valid_lat_lon_mcc_triples = [
            (FREMONT_LAT, FREMONT_LON, USA_MCC),
            (SAO_PAULO_LAT, SAO_PAULO_LON, BRAZIL_MCC),
            (PARIS_LAT, PARIS_LON, FRANCE_MCC)]

        self.invalid_latitudes = [-100.0, -85.0511, 85.0511, 100.0]
        self.invalid_longitudes = [-190.0, -180.1, 180.1, 190]

        self.valid_accuracies = [0, 1, 100, 10000]
        self.invalid_accuracies = [-10, -1, 5000000]

        self.valid_altitudes = [-100, -1, 0, 10, 100]
        self.invalid_altitudes = [-20000, 200000]

        self.valid_altitude_accuracies = [0, 1, 100, 1000]
        self.invalid_altitude_accuracies = [-10, -1, 500000]

        self.valid_asus = [0, 10, 31, 97]
        self.invalid_asus = [-10, -1, 99]

        self.valid_tas = [0, 15, 63]
        self.invalid_tas = [-10, -1, 64, 100]

        self.valid_signals = [-150, -100, -1]
        self.invalid_signals = [-300, -151, 0, 10]

    def test_all_radio_values(self):
        for (radio, v) in self.radio_pairs:
            (measure, cell) = self.make_cell_submission(radio=radio)
            self.check_normalized_cell(measure, cell, dict(radio=v))

    def test_all_valid_lat_lon_mcc_mnc_groups(self):
        for (lat, lon, mcc) in self.valid_lat_lon_mcc_triples:
            for mnc in self.valid_mncs:
                (measure, cell) = self.make_cell_submission(
                    lat=lat, lon=lon, mcc=mcc, mnc=mnc)
                self.check_normalized_cell(measure, cell, dict(lat=lat,
                                                               lon=lon,
                                                               mcc=mcc,
                                                               mnc=mnc))
            for mnc in self.valid_cdma_mncs:
                (measure, cell) = self.make_cell_submission(
                    lat=lat, lon=lon, mcc=mcc, mnc=mnc, radio='cdma')
                self.check_normalized_cell(measure, cell, dict(lat=lat,
                                                               lon=lon,
                                                               mcc=mcc,
                                                               mnc=mnc))

    def test_outside_of_country_lat_lon(self):
        (measure, cell) = self.make_cell_submission(
            mcc=USA_MCC, lat=PARIS_LAT, lon=PARIS_LON)
        self.check_normalized_cell(measure, cell, None)

    def test_all_invalid_mcc_variants_individually(self):
        for mcc in self.invalid_mccs:
            (measure, cell) = self.make_cell_submission(mcc=mcc)
            self.check_normalized_cell(measure, cell, None)

    def test_all_invalid_mnc_variants_individually(self):
        for mnc in self.invalid_mncs:
            (measure, cell) = self.make_cell_submission(mnc=mnc)
            self.check_normalized_cell(measure, cell, None)

    def test_all_valid_lac_cid_pairs_with_invalid_pscs(self):
        for lac in self.valid_lacs:
            for cid in self.valid_cids:
                for psc in self.invalid_pscs:
                    (measure, cell) = self.make_cell_submission(
                        lac=lac, cid=cid, psc=psc)
                    self.check_normalized_cell(measure, cell, dict(lac=lac,
                                                                   cid=cid,
                                                                   psc=-1))

    def test_all_invalid_lacs_with_an_invalid_psc(self):
        for lac in self.invalid_lacs:
            for psc in self.invalid_pscs:
                (measure, cell) = self.make_cell_submission(lac=lac, psc=psc)
                self.check_normalized_cell(measure, cell, None)

    def test_all_invalid_cids_with_an_invalid_psc(self):
        for cid in self.invalid_cids:
            for psc in self.invalid_pscs:
                (measure, cell) = self.make_cell_submission(cid=cid, psc=psc)
                self.check_normalized_cell(measure, cell, None)

    def test_all_invalid_lacs_with_a_valid_psc(self):
        for lac in self.invalid_lacs:
            for psc in self.valid_pscs:
                (measure, cell) = self.make_cell_submission(lac=lac, psc=psc)
                self.check_normalized_cell(measure, cell, dict(lac=-1,
                                                               psc=psc))

    def test_all_invalid_cids_with_a_valid_psc(self):
        for cid in self.invalid_cids:
            for psc in self.valid_pscs:
                (measure, cell) = self.make_cell_submission(cid=cid, psc=psc)
                self.check_normalized_cell(measure, cell, dict(cid=-1,
                                                               psc=psc))

    def test_special_invalid_lac_cid_65535_combination(self):
        (measure, cell) = self.make_cell_submission(lac=0, cid=65535)
        self.check_normalized_cell(measure, cell, None)

    def test_all_invalid_latitudes_individually(self):
        for lat in self.invalid_latitudes:
            (measure, cell) = self.make_cell_submission(lat=lat)
            self.check_normalized_cell(measure, cell, None)

    def test_all_invalid_longitudes_individually(self):
        for lon in self.invalid_longitudes:
            (measure, cell) = self.make_cell_submission(lon=lon)
            self.check_normalized_cell(measure, cell, None)

    def test_all_nice_to_have_valid_fields_individually(self):
        for (k, vs) in [('accuracy', self.valid_accuracies),
                        ('altitude', self.valid_altitudes),
                        ('altitude_accuracy', self.valid_altitude_accuracies),
                        ('asu', self.valid_asus),
                        ('ta', self.valid_tas),
                        ('signal', self.valid_signals)]:
            for v in vs:
                (measure, cell) = self.make_cell_submission(**{k: v})
                self.check_normalized_cell(measure, cell, {k: v})

    def test_all_nice_to_have_invalid_fields_individually(self):
        for (k, vs, x) in [('accuracy', self.invalid_accuracies, 0),
                           ('altitude', self.invalid_altitudes, 0),
                           ('altitude_accuracy',
                            self.invalid_altitude_accuracies, 0),
                           ('asu', self.invalid_asus, -1),
                           ('ta', self.invalid_tas, 0),
                           ('signal', self.invalid_signals, 0)]:
            for v in vs:
                (measure, cell) = self.make_cell_submission(**{k: v})
                self.check_normalized_cell(measure, cell, {k: x})

    def test_asu_signal_field_mix_up(self):
        (measure, cell) = self.make_cell_submission(asu=-75, signal=0)
        self.check_normalized_cell(measure, cell, {'signal': -75})

    def test_cid_65535_without_a_valid_lac_sets_cid_to_invalid(self):
        (measure, cell) = self.make_cell_submission(cid=65535, lac=-1, psc=1)
        self.check_normalized_cell(measure, cell, {'cid': -1})

    def test_CDMA_cell_records_must_have_MNC_MCC_LAC_CID(self):
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

    def test_records_fail_the_mcc_check(self):
        entries = [
            {'mcc': 0, 'mnc': 2, 'lac': 3, 'cid': 4},
            {'mcc': -1, 'mnc': 2, 'lac': 3, 'cid': 4},
            {'mcc': -2, 'mnc': 2, 'lac': 3, 'cid': 4},
            {'mcc': 2000, 'mnc': 2, 'lac': 3, 'cid': 4},

        ]

        for entry in entries:
            if 'radio' not in entry:
                entry['radio'] = 'cdma'
            (measure, cell) = self.make_cell_submission(**entry)
            self.check_normalized_cell(measure, cell, None)

    def test_records_fail_the_mnc_check(self):
        entries = [
            {'mcc': FRANCE_MCC, 'mnc': -1, 'lac': 3, 'cid': 4},
            {'mcc': FRANCE_MCC, 'mnc': -2, 'lac': 3, 'cid': 4},
            {'mcc': FRANCE_MCC, 'mnc': 33000, 'lac': 3, 'cid': 4},

        ]

        for entry in entries:
            if 'radio' not in entry:
                entry['radio'] = 'cdma'
            (measure, cell) = self.make_cell_submission(**entry)
            self.check_normalized_cell(measure, cell, None)

    def test_records_fail_the_lac_check(self):
        entries = [
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': -1, 'cid': 4},
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': -2, 'cid': 4},
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 65536, 'cid': 4},

        ]

        for entry in entries:
            if 'radio' not in entry:
                entry['radio'] = 'cdma'
            (measure, cell) = self.make_cell_submission(**entry)
            self.check_normalized_cell(measure, cell, None)

    def test_records_fail_the_cid_check(self):
        entries = [
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 3, 'cid': -1},
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 3, 'cid': -2},
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 3, 'cid': 2 ** 28},

        ]

        for entry in entries:
            if 'radio' not in entry:
                entry['radio'] = 'cdma'
            (measure, cell) = self.make_cell_submission(**entry)
            self.check_normalized_cell(measure, cell, None)

    def test_records_fail_the_lac_or_cid_and_psc_check(self):
        entries = [
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': -1, 'cid': -1},
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 3, 'cid': -1},
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': -1, 'cid': 4},

        ]

        for entry in entries:
            if 'radio' not in entry:
                entry['radio'] = 'cdma'
            (measure, cell) = self.make_cell_submission(**entry)
            self.check_normalized_cell(measure, cell, None)

    def test_unknown_lac_cid_is_65535_and_missing_psc(self):
        entries = [
            {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 0, 'cid': 65535, 'psc': -1},

        ]

        for entry in entries:
            if 'radio' not in entry:
                entry['radio'] = 'cdma'
            (measure, cell) = self.make_cell_submission(**entry)
            self.check_normalized_cell(measure, cell, None)

    def test_fails_because_it_has_an_MNC_above_1000_for_a_GSM_network(self):
        entries = [
            {'mcc': FRANCE_MCC, 'mnc': 1001, 'lac': 3, 'cid': 4,
             'radio': 'gsm'},
        ]

        for entry in entries:
            if 'radio' not in entry:
                entry['radio'] = 'cdma'
            (measure, cell) = self.make_cell_submission(**entry)
            self.check_normalized_cell(measure, cell, None)

    def test_wrong_radio_type_is_corrected_for_large_cid(self):
        measure, cell = self.make_cell_submission(cid=65536, radio='gsm')
        self.check_normalized_cell(measure, cell, {'radio': 2})


class TestWifiValidation(ValidationTest):

    def check_normalized_wifi(self, measure, wifi, expect):
        d = measure.copy()
        d.update(wifi)
        result = normalized_wifi_dict(d)

        if expect is None:
            self.assertEqual(result, expect)
        else:
            for (k, v) in expect.items():
                self.assertEqual(result[k], v)
        return result

    def make_wifi_submission(self, **kwargs):
        measure = {
            'accuracy': 120,
            'altitude': 220,
            'altitude_accuracy': 10,
            'lat': 49.25,
            'lon': 123.10,
            'radio': '',
            'time': self.time,
        }
        wifi = dict(key='12:34:56:78:90:12',
                    frequency=2442,
                    channel=7,
                    signal=-85,
                    signalToNoiseRatio=37)
        for (k, v) in kwargs.items():
            if k in measure:
                measure[k] = v
            else:
                wifi[k] = v
        return (measure, wifi)

    def setUp(self):
        self.valid_channels = [1, 20, 45, 165]
        self.invalid_channels = [-10, -1, 201, 2500]

        self.valid_frequency_channels = [
            (2412, 1),
            (2427, 4),
            (2472, 13),
            (5170, 34),
            (5200, 40),
            (5805, 161),
            (5825, 165)
        ]
        self.invalid_frequencies = [-1, 2000, 2411, 2473, 5168, 5826, 6000]

        self.valid_key_pairs = [
            ('12:34:56:78:90:12', '123456789012'),
            ('12.34.56.78.90.12', '123456789012'),
            ('1234::5678::9012', '123456789012'),
            ('a2:b4:c6:d8:e0:f2', 'a2b4c6d8e0f2'),
            ('A2:B4:C6:D8:E0:F2', 'a2b4c6d8e0f2'),
            ('1-a3-b5-c7-D9-E1-F', '1a3b5c7d9e1f'),
            ('fffffffffff0', 'fffffffffff0'),
            ('f00000000000', 'f00000000000'),
            ('000000-a00000', '000000a00000'),
            ('f1234abcd345', 'f1234abcd345'),
            # We considered but do not ban locally administered wifi keys
            # based on the U/L bit https://en.wikipedia.org/wiki/MAC_address
            ('0a:00:00:00:00:00', '0a0000000000'),
        ]
        self.invalid_keys = [
            'ab:cd',
            'ffffffffffff',
            '000000000000',
            '00000000001',
            '00000000000g',
            '12#34:56:78:90:12',
            '[1234.56.78.9012]',
        ] + [WIFI_TEST_KEY] + [
            c.join([str.format('{x:02x}', x=x)
                    for x in range(6)])
            for c in '!@#$%^&*()_+={}\x01\x02\x03\r\n']

        self.valid_signals = [-200, -100, -1]
        self.invalid_signals = [-300, -201, 0, 10]

        self.valid_snrs = [0, 12, 100]
        self.invalid_snrs = [-1, -50, 101]

    def test_valid_keys(self):
        for (k1, k2) in self.valid_key_pairs:
            (measure, wifi) = self.make_wifi_submission(key=k1)
            self.check_normalized_wifi(measure, wifi, dict(key=k2))

    def test_invalid_keys(self):
        for k in self.invalid_keys:
            (measure, wifi) = self.make_wifi_submission(key=k)
            self.check_normalized_wifi(measure, wifi, None)

    def test_valid_frequency_channel_pairs_together_and_individually(self):
        for (f, c) in self.valid_frequency_channels:
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

    def test_valid_signals(self):
        for s in self.valid_signals:
            (measure, wifi) = self.make_wifi_submission(signal=s)
            self.check_normalized_wifi(measure, wifi, dict(signal=s))

    def test_invalid_signals(self):
        for s in self.invalid_signals:
            (measure, wifi) = self.make_wifi_submission(signal=s)
            self.check_normalized_wifi(measure, wifi, dict(signal=0))

    def test_valid_snrs(self):
        for s in self.valid_snrs:
            (measure, wifi) = self.make_wifi_submission(signalToNoiseRatio=s)
            self.check_normalized_wifi(
                measure, wifi, dict(signalToNoiseRatio=s))

    def test_invalid_snrs(self):
        for s in self.invalid_snrs:
            (measure, wifi) = self.make_wifi_submission(signalToNoiseRatio=s)
            self.check_normalized_wifi(
                measure, wifi, dict(signalToNoiseRatio=0))

    def test_valid_channels(self):
        for c in self.valid_channels:
            (measure, wifi) = self.make_wifi_submission(channel=c)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

    def test_invalid_channels_are_corrected_by_valid_frequency(self):
        for c in self.invalid_channels:
            (measure, wifi) = self.make_wifi_submission()
            chan = wifi['channel']
            wifi['channel'] = c
            wifi = self.check_normalized_wifi(measure, wifi,
                                              dict(channel=chan))
            self.assertFalse('frequency' in wifi)

    def test_invalid_frequencies_have_no_effect_and_are_dropped_anyways(self):
        for f in self.invalid_frequencies:
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
            ('2011-01-01T11:12:13.456Z', now_enc),
            ('2070-01-01T11:12:13.456Z', now_enc),
            ('10-10-10', now_enc),
            ('2011-10-13T.Z', now_enc),
        ]

        for entry in entries:
            in_, expected = entry
            if not isinstance(in_, str):
                in_ = encode_datetime(in_)
            self.assertEqual(
                decode_datetime(normalized_time(in_)), expected)
