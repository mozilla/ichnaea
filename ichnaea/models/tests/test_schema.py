from datetime import timedelta
import uuid

from pytz import UTC

from ichnaea.models import (
    Radio,
    CellObservation,
    WifiObservation,
)
from ichnaea.models import constants
from ichnaea.models.schema import normalized_time
from ichnaea.tests.base import TestCase
from ichnaea import util

FRANCE_MCC = 208
VIVENDI_MNC = 10
PARIS_LAT = 48.8568
PARIS_LON = 2.3508

BRAZIL_MCC = 724
SAO_PAULO_LAT = -23.54
SAO_PAULO_LON = -46.64

USA_MCC = 310
FREMONT_LAT = 37.5079
FREMONT_LON = -121.96


class ValidationTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ValidationTest, cls).setUpClass()
        cls.time = util.utcnow()

    def check_normalized(self, validator, observation, extra, expect):
        observation = observation.copy()
        observation.update(extra)
        result = validator(observation)

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


class TestCellValidation(ValidationTest):

    def setUp(self):
        super(TestCellValidation, self).setUp()
        self.invalid_lacs = [constants.MIN_LAC - 1, constants.MAX_LAC_ALL + 1]
        self.invalid_cids = [constants.MIN_CID - 1, constants.MAX_CID_ALL + 1]

        self.valid_pscs = [0, 120, 512]
        self.invalid_pscs = [-1, 513, 4456]

    def check_normalized_cell(self, observation, cell, expect):
        return self.check_normalized(
            CellObservation.validate,
            observation, cell, expect)

    def get_sample(self, **kwargs):
        obs = {
            'accuracy': 120,
            'altitude': 220,
            'altitude_accuracy': 10,
            'lat': PARIS_LAT,
            'lon': PARIS_LON,
            'radio': Radio.gsm.name,
            'time': self.time,
            'report_id': None,
        }
        cell = {
            'asu': 15,
            'cid': 34567,
            'lac': 12345,
            'mcc': FRANCE_MCC,
            'mnc': VIVENDI_MNC,
            'psc': None,
            'signal': -83,
            'ta': 5,
        }
        for (k, v) in kwargs.items():
            if k in obs:
                obs[k] = v
            else:
                cell[k] = v
        return (obs, cell)

    def test_report_empty(self):
        obs, cell = self.get_sample(report_id='')
        result = self.check_normalized_cell(obs, cell, {})
        self.assertTrue(isinstance(result['report_id'], uuid.UUID))
        self.assertEqual(result['report_id'].version, 1)

    def test_report_none(self):
        obs, cell = self.get_sample(report_id=None)
        result = self.check_normalized_cell(obs, cell, {})
        self.assertTrue(isinstance(result['report_id'], uuid.UUID))
        self.assertEqual(result['report_id'].version, 1)

    def test_report_id(self):
        report_id = uuid.uuid1()
        obs, cell = self.get_sample(report_id=report_id)
        self.check_normalized_cell(obs, cell, dict(report_id=report_id))

    def test_report_id_string(self):
        report_id = uuid.uuid1()
        obs, cell = self.get_sample(report_id=report_id.hex)
        self.check_normalized_cell(obs, cell, dict(report_id=report_id))

    def test_report_id_number(self):
        obs, cell = self.get_sample(report_id=12)
        self.check_normalized_cell(obs, cell, None)

    def test_all_radio_values(self):
        radio_pairs = [
            ('gsm', {'radio': Radio.gsm}),
            (Radio.gsm.name, {'radio': Radio.gsm}),
            ('cdma', {'radio': Radio.cdma}),
            ('umts', {'radio': Radio.umts}),
            ('wcdma', {'radio': Radio.wcdma}),
            ('lte', {'radio': Radio.lte}),
            ('wimax', None),
            ('', None),
            ('hspa', None),
            ('n/a', None),
        ]

        for (radio, expect) in radio_pairs:
            obs, cell = self.get_sample(radio=radio)
            self.check_normalized_cell(obs, cell, expect)

    def test_all_valid_lat_lon_mcc_mnc_groups(self):
        valid_lat_lon_mcc_triples = [
            (FREMONT_LAT, FREMONT_LON, USA_MCC),
            (SAO_PAULO_LAT, SAO_PAULO_LON, BRAZIL_MCC),
            (PARIS_LAT, PARIS_LON, FRANCE_MCC),
        ]
        valid_mncs = [0, 542, 999]
        valid_cdma_mncs = [0, 542, 32767]

        for (lat, lon, mcc) in valid_lat_lon_mcc_triples:
            for mnc in valid_mncs:
                obs, cell = self.get_sample(
                    lat=lat, lon=lon, mcc=mcc, mnc=mnc)
                self.check_normalized_cell(
                    obs, cell, dict(lat=lat, lon=lon, mcc=mcc, mnc=mnc))
            for mnc in valid_cdma_mncs:
                obs, cell = self.get_sample(
                    lat=lat, lon=lon, mcc=mcc, mnc=mnc, radio=Radio.cdma.name)
                self.check_normalized_cell(
                    obs, cell, dict(lat=lat, lon=lon, mcc=mcc, mnc=mnc))

    def test_outside_of_country_lat_lon(self):
        obs, cell = self.get_sample(
            mcc=USA_MCC, lat=PARIS_LAT, lon=PARIS_LON)
        self.check_normalized_cell(obs, cell, None)

    def test_invalid_mcc(self):
        invalid_mccs = [-10, -1, 0, 101, 1000, 3456]
        for mcc in invalid_mccs:
            obs, cell = self.get_sample(mcc=mcc)
            self.check_normalized_cell(obs, cell, None)

    def test_invalid_mnc(self):
        invalid_mncs = [-10, -1, 32768, 93870]
        for mnc in invalid_mncs:
            obs, cell = self.get_sample(mnc=mnc)
            self.check_normalized_cell(obs, cell, None)

    def test_valid_lac_cid_pairs_with_invalid_psc(self):
        valid_lacs = [constants.MIN_LAC, constants.MAX_LAC_GSM_UMTS_LTE]
        valid_cids = [constants.MIN_CID, constants.MAX_CID_ALL]
        for lac in valid_lacs:
            for cid in valid_cids:
                for psc in self.invalid_pscs:
                    obs, cell = self.get_sample(
                        lac=lac, cid=cid, psc=psc)
                    self.check_normalized_cell(
                        obs, cell, dict(lac=lac, cid=cid, psc=None))

    def test_invalid_lac_with_an_invalid_psc(self):
        for lac in self.invalid_lacs:
            for psc in self.invalid_pscs:
                obs, cell = self.get_sample(lac=lac, psc=psc)
                self.check_normalized_cell(obs, cell, None)

    def test_invalid_lac_with_a_valid_psc(self):
        for lac in self.invalid_lacs:
            for psc in self.valid_pscs:
                obs, cell = self.get_sample(lac=lac, psc=psc)
                self.check_normalized_cell(
                    obs, cell, dict(lac=None, psc=psc))

    def test_invalid_cid_with_an_invalid_psc(self):
        for cid in self.invalid_cids:
            for psc in self.invalid_pscs:
                obs, cell = self.get_sample(cid=cid, psc=psc)
                self.check_normalized_cell(obs, cell, None)

    def test_invalid_cid_with_a_valid_psc(self):
        for cid in self.invalid_cids:
            for psc in self.valid_pscs:
                obs, cell = self.get_sample(cid=cid, psc=psc)
                self.check_normalized_cell(
                    obs, cell, dict(cid=None, psc=psc))

    def test_invalid_latitude(self):
        invalid_latitudes = [constants.MIN_LAT - 0.1, constants.MAX_LAT + 0.1]
        for lat in invalid_latitudes:
            obs, cell = self.get_sample(lat=lat)
            self.check_normalized_cell(obs, cell, None)

    def test_invalid_longitude(self):
        invalid_longitudes = [constants.MIN_LON - 0.1, constants.MAX_LON + 0.1]
        for lon in invalid_longitudes:
            obs, cell = self.get_sample(lon=lon)
            self.check_normalized_cell(obs, cell, None)

    def test_valid_accuracy(self):
        valid_accuracies = [0, 1, 100, 10000]
        for accuracy in valid_accuracies:
            obs, cell = self.get_sample(accuracy=accuracy)
            self.check_normalized_cell(obs, cell, {'accuracy': accuracy})

    def test_valid_altitude(self):
        valid_altitudes = [-100, -1, 0, 10, 100]
        for altitude in valid_altitudes:
            obs, cell = self.get_sample(altitude=altitude)
            self.check_normalized_cell(obs, cell, {'altitude': altitude})

    def test_valid_altitude_accuracy(self):
        valid_altitude_accuracies = [0, 1, 100, 1000]
        for altitude_accuracy in valid_altitude_accuracies:
            obs, cell = self.get_sample(
                altitude_accuracy=altitude_accuracy)
            self.check_normalized_cell(
                obs, cell, {'altitude_accuracy': altitude_accuracy})

    def test_valid_asu(self):
        valid_asus = [0, 10, 31, 97]
        for asu in valid_asus:
            obs, cell = self.get_sample(asu=asu)
            self.check_normalized_cell(obs, cell, {'asu': asu})

    def test_valid_ta(self):
        valid_tas = [0, 15, 63]
        for ta in valid_tas:
            obs, cell = self.get_sample(ta=ta)
            self.check_normalized_cell(obs, cell, {'ta': ta})

    def test_valid_signal(self):
        valid_signals = [-150, -100, -1]
        for signal in valid_signals:
            obs, cell = self.get_sample(signal=signal)
            self.check_normalized_cell(obs, cell, {'signal': signal})

    def test_valid_time(self):
        now = util.utcnow()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0)
        obs, cell = self.get_sample(time=now)
        self.check_normalized_cell(obs, cell, {'time': first_of_month})

    def test_invalid_accuracy(self):
        invalid_accuracies = [-10, -1, 5000000]
        for accuracy in invalid_accuracies:
            obs, cell = self.get_sample(accuracy=accuracy)
            self.check_normalized_cell(obs, cell, {'accuracy': None})

    def test_invalid_altitude(self):
        invalid_altitudes = [-20000, 200000]
        for altitude in invalid_altitudes:
            obs, cell = self.get_sample(altitude=altitude)
            self.check_normalized_cell(obs, cell, {'altitude': None})

    def test_invalid_altitude_accuracy(self):
        invalid_altitude_accuracies = [-10, -1, 500000]
        for altitude_accuracy in invalid_altitude_accuracies:
            obs, cell = self.get_sample(
                altitude_accuracy=altitude_accuracy)
            self.check_normalized_cell(
                obs, cell, {'altitude_accuracy': None})

    def test_invalid_asu(self):
        invalid_asus = [-10, -1, 99]
        for asu in invalid_asus:
            obs, cell = self.get_sample(asu=asu)
            self.check_normalized_cell(obs, cell, {'asu': None})

    def test_invalid_ta(self):
        invalid_tas = [-10, -1, 64, 100]
        for ta in invalid_tas:
            obs, cell = self.get_sample(ta=ta)
            self.check_normalized_cell(obs, cell, {'ta': None})

    def test_invalid_signal(self):
        invalid_signals = [-300, -151, 0, 10]
        for signal in invalid_signals:
            obs, cell = self.get_sample(signal=signal)
            self.check_normalized_cell(obs, cell, {'signal': None})

    def test_asu_signal_field_mix_up(self):
        obs, cell = self.get_sample(asu=-75, signal=0)
        self.check_normalized_cell(obs, cell, {'signal': -75})

    def test_cid_65535_without_a_valid_lac_sets_cid_to_invalid(self):
        obs, cell = self.get_sample(lac=None, cid=65535, psc=1)
        self.check_normalized_cell(obs, cell, {'cid': None})

    def test_unknown_lac_cid_is_65535_and_missing_psc(self):
        obs, cell = self.get_sample(lac=None, cid=65535, psc=None)
        self.check_normalized_cell(obs, cell, None)

    def test_cdma_cell_records_must_have_full_cell_id(self):
        entries = [
            # (data-in, data-out)
            ({'lac': 3, 'cid': 4}, {'lac': 3, 'cid': 4}),
            ({'lac': 3, 'cid': None}, None),
            ({'lac': None, 'cid': 4}, None),
            ({'lac': None, 'cid': None, 'psc': 5}, None),
        ]

        for entry in entries:
            obs, cell = self.get_sample(
                radio=Radio.cdma.name, **entry[0])
            self.check_normalized_cell(obs, cell, entry[1])

    def test_records_fail_the_lac_or_cid_and_psc_check(self):
        entries = [
            {'lac': None, 'cid': None},
            {'lac': 3, 'cid': None},
            {'lac': None, 'cid': 4},
        ]

        for entry in entries:
            obs, cell = self.get_sample(**entry)
            self.check_normalized_cell(obs, cell, None)

    def test_mnc_above_1000_for_a_gsm_network(self):
        obs, cell = self.get_sample(radio=Radio.gsm.name, mnc=1001)
        self.check_normalized_cell(obs, cell, None)

    def test_wrong_gsm_radio_type_is_corrected_for_large_cid(self):
        obs, cell = self.get_sample(radio=Radio.gsm.name, cid=65536)
        self.check_normalized_cell(
            obs, cell, {'radio': Radio.umts})

    def test_valid_umts_cid_is_32_bit(self):
        valid_cid = constants.MAX_CID_ALL
        obs, cell = self.get_sample(
            radio=Radio.umts.name, cid=valid_cid)
        self.check_normalized_cell(obs, cell, {'cid': valid_cid})

    def test_invalid_umts_cid_is_not_32_bit(self):
        invalid_cid = constants.MAX_CID_ALL + 1
        obs, cell = self.get_sample(
            radio=Radio.umts.name, cid=invalid_cid)
        self.check_normalized_cell(obs, cell, None)

    def test_valid_cdma_cid_is_16_bit(self):
        valid_cid = constants.MAX_CID_CDMA
        obs, cell = self.get_sample(
            radio=Radio.cdma.name, cid=valid_cid)
        self.check_normalized_cell(obs, cell, {'cid': valid_cid})

    def test_invalid_cdma_cid_is_not_16_bit(self):
        invalid_cid = constants.MAX_CID_CDMA + 1
        obs, cell = self.get_sample(
            radio=Radio.cdma.name, cid=invalid_cid)
        self.check_normalized_cell(obs, cell, None)

    def test_valid_lte_cid_is_28_bit(self):
        valid_cid = constants.MAX_CID_LTE
        obs, cell = self.get_sample(
            radio=Radio.lte.name, cid=valid_cid)
        self.check_normalized_cell(obs, cell, {'cid': valid_cid})

    def test_invalid_lte_cid_is_not_28_bit(self):
        invalid_cid = constants.MAX_CID_LTE + 1
        obs, cell = self.get_sample(
            radio=Radio.lte.name, cid=invalid_cid)
        self.check_normalized_cell(obs, cell, None)

    def test_valid_lac_for_gsm_family_is_less_or_equal_to_65533(self):
        valid_lac = constants.MAX_LAC_GSM_UMTS_LTE
        for radio in Radio._gsm_family():
            obs, cell = self.get_sample(
                radio=radio.name, lac=valid_lac)
            self.check_normalized_cell(obs, cell, {'lac': valid_lac})

    def test_invalid_lac_for_gsm_family_is_greater_than_65533(self):
        invalid_lac = constants.MAX_LAC_GSM_UMTS_LTE + 1
        for radio in Radio._gsm_family():
            obs, cell = self.get_sample(
                radio=radio.name, lac=invalid_lac)
            self.check_normalized_cell(obs, cell, None)

    def test_valid_lac_for_cdma_is_less_or_equal_to_65534(self):
        valid_lac = constants.MAX_LAC_ALL
        obs, cell = self.get_sample(
            radio=Radio.cdma.name, lac=valid_lac)
        self.check_normalized_cell(obs, cell, {'lac': valid_lac})

    def test_invalid_lac_for_cdma_is_greater_than_65534(self):
        invalid_lac = constants.MAX_LAC_ALL + 1
        obs, cell = self.get_sample(
            radio=Radio.cdma.name, lac=invalid_lac)
        self.check_normalized_cell(obs, cell, None)


class TestWifiValidation(ValidationTest):

    def check_normalized_wifi(self, obs, wifi, expect):
        return self.check_normalized(
            WifiObservation.validate,
            obs, wifi, expect)

    def get_sample(self, **kwargs):
        obs = {
            'accuracy': 120,
            'altitude': 220,
            'altitude_accuracy': 10,
            'lat': 49.25,
            'lon': 123.10,
            'radio': '',
            'time': self.time,
        }
        wifi = {
            'key': '12:34:56:78:90:12',
            'frequency': 2442,
            'channel': 7,
            'signal': -85,
            'snr': 37,
        }
        for (k, v) in kwargs.items():
            if k in obs:
                obs[k] = v
            else:
                wifi[k] = v
        return (obs, wifi)

    def test_valid_key(self):
        valid_key_pairs = [
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

        for (in_, out) in valid_key_pairs:
            obs, wifi = self.get_sample(key=in_)
            self.check_normalized_wifi(obs, wifi, dict(key=out))

    def test_invalid_key(self):
        invalid_keys = [
            'ab:cd',
            'ffffffffffff',
            '000000000000',
            '00000000001',
            '00000000000g',
            '12#34:56:78:90:12',
            '[1234.56.78.9012]',
        ] + [constants.WIFI_TEST_KEY] + [
            c.join([str.format('{x:02x}', x=x)
                    for x in range(6)])
            for c in '!@#$%^&*()_+={}\x01\x02\x03\r\n']

        for key in invalid_keys:
            obs, wifi = self.get_sample(key=key)
            self.check_normalized_wifi(obs, wifi, None)

    def test_valid_frequency_channel_pairs(self):
        valid_frequency_channels = [
            (2412, 1),
            (2427, 4),
            (2472, 13),
            (5170, 34),
            (5200, 40),
            (5805, 161),
            (5825, 165)
        ]

        for (f, c) in valid_frequency_channels:
            obs, wifi = self.get_sample(
                frequency=f, channel=c)
            wifi = self.check_normalized_wifi(obs, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

            obs, wifi = self.get_sample(
                frequency=f, channel=0)
            wifi = self.check_normalized_wifi(obs, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

            obs, wifi = self.get_sample(
                frequency=0, channel=c)
            wifi = self.check_normalized_wifi(obs, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

    def test_valid_signal(self):
        valid_signals = [-200, -100, -1]

        for signal in valid_signals:
            obs, wifi = self.get_sample(signal=signal)
            self.check_normalized_wifi(obs, wifi, dict(signal=signal))

    def test_invalid_signal(self):
        invalid_signals = [-300, -201, 0, 10]

        for signal in invalid_signals:
            obs, wifi = self.get_sample(signal=signal)
            self.check_normalized_wifi(obs, wifi, dict(signal=None))

    def test_valid_snr(self):
        valid_snrs = [0, 12, 100]

        for snr in valid_snrs:
            obs, wifi = self.get_sample(snr=snr)
            self.check_normalized_wifi(obs, wifi, dict(snr=snr))

    def test_invalid_snr(self):
        invalid_snrs = [-1, -50, 101]

        for snr in invalid_snrs:
            obs, wifi = self.get_sample(snr=snr)
            self.check_normalized_wifi(obs, wifi, dict(snr=None))

    def test_valid_channel(self):
        valid_channels = [1, 20, 45, 165]

        for channel in valid_channels:
            obs, wifi = self.get_sample(channel=channel)
            wifi = self.check_normalized_wifi(
                obs, wifi, dict(channel=channel))
            self.assertFalse('frequency' in wifi)

    def test_invalid_channel_is_corrected_by_valid_frequency(self):
        invalid_channels = [-10, -1, 201, 2500]

        for channel in invalid_channels:
            obs, wifi = self.get_sample()
            chan = wifi['channel']
            wifi['channel'] = channel
            wifi = self.check_normalized_wifi(obs, wifi,
                                              dict(channel=chan))
            self.assertFalse('frequency' in wifi)

    def test_invalid_frequency_has_no_effect_and_is_dropped(self):
        invalid_frequencies = [-1, 2000, 2411, 2473, 5168, 5826, 6000]

        for frequency in invalid_frequencies:
            obs, wifi = self.get_sample(frequency=frequency)
            chan = wifi['channel']
            wifi = self.check_normalized_wifi(obs, wifi,
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
            (now.date(), now_enc),
            (two_weeks_ago, two_weeks_ago.replace(**first_args)),
            (short_format, now_enc),
            ('2011-01-01T11:12:13.456Z', now_enc),
            ('2070-01-01T11:12:13.456Z', now_enc),
            ('10-10-10', now_enc),
            ('2011-10-13T.Z', now_enc),
        ]

        for entry in entries:
            in_, expected = entry
            self.assertEqual(normalized_time(in_), expected)
