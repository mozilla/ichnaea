from datetime import timedelta
import uuid

from pytz import UTC

from ichnaea.data import constants
from ichnaea.data.schema import normalized_time, ValidCellBaseSchema
from ichnaea.data.validation import (
    normalized_cell_measure_dict,
    normalized_wifi_dict,
)
from ichnaea.models import RADIO_TYPE
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
        cls.time = util.utcnow()

    def check_normalized(self, validator, measure, extra, expect):
        measure = measure.copy()
        measure.update(extra)
        result = validator(measure)

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
        self.invalid_lacs = [constants.MIN_LAC - 1, constants.MAX_LAC_ALL + 1]
        self.invalid_cids = [constants.MIN_CID - 1, constants.MAX_CID_ALL + 1]

        self.valid_pscs = [0, 120, 512]
        self.invalid_pscs = [-1, 513, 4456]

    def check_normalized_cell(self, measure, cell, expect):
        return self.check_normalized(
            normalized_cell_measure_dict,
            measure, cell, expect)

    def get_sample_measure_cell(self, **kwargs):
        measure = {
            'accuracy': 120,
            'altitude': 220,
            'altitude_accuracy': 10,
            'lat': PARIS_LAT,
            'lon': PARIS_LON,
            'radio': 'gsm',
            'time': self.time,
            'report_id': None,
        }
        cell = {
            'asu': 15,
            'cid': 34567,
            'lac': 12345,
            'mcc': FRANCE_MCC,
            'mnc': 220,
            'psc': -1,
            'signal': -83,
            'ta': 5,
        }
        for (k, v) in kwargs.items():
            if k in measure:
                measure[k] = v
            else:
                cell[k] = v
        return (measure, cell)

    def test_report_empty(self):
        measure, cell = self.get_sample_measure_cell(report_id='')
        result = self.check_normalized_cell(measure, cell, {})
        self.assertTrue(isinstance(result['report_id'], uuid.UUID))
        self.assertEqual(result['report_id'].version, 1)

    def test_report_none(self):
        measure, cell = self.get_sample_measure_cell(report_id=None)
        result = self.check_normalized_cell(measure, cell, {})
        self.assertTrue(isinstance(result['report_id'], uuid.UUID))
        self.assertEqual(result['report_id'].version, 1)

    def test_report_id(self):
        report_id = uuid.uuid1()
        measure, cell = self.get_sample_measure_cell(report_id=report_id)
        self.check_normalized_cell(measure, cell, dict(report_id=report_id))

    def test_report_id_string(self):
        report_id = uuid.uuid1()
        measure, cell = self.get_sample_measure_cell(report_id=report_id.hex)
        self.check_normalized_cell(measure, cell, dict(report_id=report_id))

    def test_report_id_number(self):
        measure, cell = self.get_sample_measure_cell(report_id=12)
        self.check_normalized_cell(measure, cell, None)

    def test_all_radio_values(self):
        radio_pairs = [
            ('gsm', RADIO_TYPE['gsm']),
            ('cdma', RADIO_TYPE['cdma']),
            ('umts', RADIO_TYPE['umts']),
            ('wcdma', RADIO_TYPE['wcdma']),
            ('lte', RADIO_TYPE['lte']),
            ('wimax', -1),
            ('', -1),
            ('hspa', -1),
            ('n/a', -1),
        ]

        for (radio, v) in radio_pairs:
            measure, cell = self.get_sample_measure_cell(radio=radio)
            self.check_normalized_cell(measure, cell, dict(radio=v))

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
                measure, cell = self.get_sample_measure_cell(
                    lat=lat, lon=lon, mcc=mcc, mnc=mnc)
                self.check_normalized_cell(
                    measure, cell, dict(lat=lat, lon=lon, mcc=mcc, mnc=mnc))
            for mnc in valid_cdma_mncs:
                measure, cell = self.get_sample_measure_cell(
                    lat=lat, lon=lon, mcc=mcc, mnc=mnc, radio='cdma')
                self.check_normalized_cell(
                    measure, cell, dict(lat=lat, lon=lon, mcc=mcc, mnc=mnc))

    def test_outside_of_country_lat_lon(self):
        measure, cell = self.get_sample_measure_cell(
            mcc=USA_MCC, lat=PARIS_LAT, lon=PARIS_LON)
        self.check_normalized_cell(measure, cell, None)

    def test_invalid_mcc(self):
        invalid_mccs = [-10, -1, 0, 101, 1000, 3456]
        for mcc in invalid_mccs:
            measure, cell = self.get_sample_measure_cell(mcc=mcc)
            self.check_normalized_cell(measure, cell, None)

    def test_invalid_mnc(self):
        invalid_mncs = [-10, -1, 32768, 93870]
        for mnc in invalid_mncs:
            measure, cell = self.get_sample_measure_cell(mnc=mnc)
            self.check_normalized_cell(measure, cell, None)

    def test_valid_lac_cid_pairs_with_invalid_psc(self):
        valid_lacs = [constants.MIN_LAC, constants.MAX_LAC_GSM_UMTS_LTE]
        valid_cids = [constants.MIN_CID, constants.MAX_CID_ALL]
        for lac in valid_lacs:
            for cid in valid_cids:
                for psc in self.invalid_pscs:
                    measure, cell = self.get_sample_measure_cell(
                        lac=lac, cid=cid, psc=psc)
                    self.check_normalized_cell(
                        measure, cell, dict(lac=lac, cid=cid, psc=-1))

    def test_invalid_lac_with_an_invalid_psc(self):
        for lac in self.invalid_lacs:
            for psc in self.invalid_pscs:
                measure, cell = self.get_sample_measure_cell(lac=lac, psc=psc)
                self.check_normalized_cell(measure, cell, None)

    def test_invalid_lac_with_a_valid_psc(self):
        schema = ValidCellBaseSchema()
        for lac in self.invalid_lacs:
            for psc in self.valid_pscs:
                measure, cell = self.get_sample_measure_cell(lac=lac, psc=psc)
                self.check_normalized_cell(
                    measure, cell, dict(
                        lac=schema.fields['lac'].missing, psc=psc))

    def test_invalid_cid_with_an_invalid_psc(self):
        for cid in self.invalid_cids:
            for psc in self.invalid_pscs:
                measure, cell = self.get_sample_measure_cell(cid=cid, psc=psc)
                self.check_normalized_cell(measure, cell, None)

    def test_invalid_cid_with_a_valid_psc(self):
        schema = ValidCellBaseSchema()
        for cid in self.invalid_cids:
            for psc in self.valid_pscs:
                measure, cell = self.get_sample_measure_cell(cid=cid, psc=psc)
                self.check_normalized_cell(
                    measure, cell, dict(
                        cid=schema.fields['cid'].missing, psc=psc))

    def test_invalid_latitude(self):
        invalid_latitudes = [constants.MIN_LAT - 0.1, constants.MAX_LAT + 0.1]
        for lat in invalid_latitudes:
            measure, cell = self.get_sample_measure_cell(lat=lat)
            self.check_normalized_cell(measure, cell, None)

    def test_invalid_longitude(self):
        invalid_longitudes = [constants.MIN_LON - 0.1, constants.MAX_LON + 0.1]
        for lon in invalid_longitudes:
            measure, cell = self.get_sample_measure_cell(lon=lon)
            self.check_normalized_cell(measure, cell, None)

    def test_valid_accuracy(self):
        valid_accuracies = [0, 1, 100, 10000]
        for accuracy in valid_accuracies:
            measure, cell = self.get_sample_measure_cell(accuracy=accuracy)
            self.check_normalized_cell(measure, cell, {'accuracy': accuracy})

    def test_valid_altitude(self):
        valid_altitudes = [-100, -1, 0, 10, 100]
        for altitude in valid_altitudes:
            measure, cell = self.get_sample_measure_cell(altitude=altitude)
            self.check_normalized_cell(measure, cell, {'altitude': altitude})

    def test_valid_altitude_accuracy(self):
        valid_altitude_accuracies = [0, 1, 100, 1000]
        for altitude_accuracy in valid_altitude_accuracies:
            measure, cell = self.get_sample_measure_cell(
                altitude_accuracy=altitude_accuracy)
            self.check_normalized_cell(
                measure, cell, {'altitude_accuracy': altitude_accuracy})

    def test_valid_asu(self):
        valid_asus = [0, 10, 31, 97]
        for asu in valid_asus:
            measure, cell = self.get_sample_measure_cell(asu=asu)
            self.check_normalized_cell(measure, cell, {'asu': asu})

    def test_valid_ta(self):
        valid_tas = [0, 15, 63]
        for ta in valid_tas:
            measure, cell = self.get_sample_measure_cell(ta=ta)
            self.check_normalized_cell(measure, cell, {'ta': ta})

    def test_valid_signal(self):
        valid_signals = [-150, -100, -1]
        for signal in valid_signals:
            measure, cell = self.get_sample_measure_cell(signal=signal)
            self.check_normalized_cell(measure, cell, {'signal': signal})

    def test_valid_time(self):
        now = util.utcnow()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0)
        measure, cell = self.get_sample_measure_cell(time=now)
        self.check_normalized_cell(measure, cell, {'time': first_of_month})

    def test_invalid_accuracy(self):
        invalid_accuracies = [-10, -1, 5000000]
        for accuracy in invalid_accuracies:
            measure, cell = self.get_sample_measure_cell(accuracy=accuracy)
            self.check_normalized_cell(measure, cell, {'accuracy': 0})

    def test_invalid_altitude(self):
        invalid_altitudes = [-20000, 200000]
        for altitude in invalid_altitudes:
            measure, cell = self.get_sample_measure_cell(altitude=altitude)
            self.check_normalized_cell(measure, cell, {'altitude': 0})

    def test_invalid_altitude_accuracy(self):
        invalid_altitude_accuracies = [-10, -1, 500000]
        for altitude_accuracy in invalid_altitude_accuracies:
            measure, cell = self.get_sample_measure_cell(
                altitude_accuracy=altitude_accuracy)
            self.check_normalized_cell(
                measure, cell, {'altitude_accuracy': 0})

    def test_invalid_asu(self):
        invalid_asus = [-10, -1, 99]
        for asu in invalid_asus:
            measure, cell = self.get_sample_measure_cell(asu=asu)
            self.check_normalized_cell(measure, cell, {'asu': -1})

    def test_invalid_ta(self):
        invalid_tas = [-10, -1, 64, 100]
        for ta in invalid_tas:
            measure, cell = self.get_sample_measure_cell(ta=ta)
            self.check_normalized_cell(measure, cell, {'ta': 0})

    def test_invalid_signal(self):
        invalid_signals = [-300, -151, 0, 10]
        for signal in invalid_signals:
            measure, cell = self.get_sample_measure_cell(signal=signal)
            self.check_normalized_cell(measure, cell, {'signal': 0})

    def test_asu_signal_field_mix_up(self):
        measure, cell = self.get_sample_measure_cell(asu=-75, signal=0)
        self.check_normalized_cell(measure, cell, {'signal': -75})

    def test_cid_65535_without_a_valid_lac_sets_cid_to_invalid(self):
        schema = ValidCellBaseSchema()
        measure, cell = self.get_sample_measure_cell(
            lac=schema.fields['lac'].missing, cid=65535, psc=1)
        self.check_normalized_cell(
            measure, cell, {'cid': schema.fields['cid'].missing})

    def test_unknown_lac_cid_is_65535_and_missing_psc(self):
        measure, cell = self.get_sample_measure_cell(lac=0, cid=65535, psc=-1)
        self.check_normalized_cell(measure, cell, None)

    def test_cdma_cell_records_must_have_full_cell_id(self):
        entries = [
            # (data-in, data-out)
            ({'lac': 3, 'cid': 4}, {'lac': 3, 'cid': 4}),
            ({'lac': 3, 'cid': -1}, None),
            ({'lac': -1, 'cid': 4}, None),
            ({'lac': -1, 'cid': -1, 'psc': 5}, None),
        ]

        for entry in entries:
            measure, cell = self.get_sample_measure_cell(
                radio='cdma', **entry[0])
            self.check_normalized_cell(measure, cell, entry[1])

    def test_records_fail_the_lac_or_cid_and_psc_check(self):
        entries = [
            {'lac': -1, 'cid': -1},
            {'lac': 3, 'cid': -1},
            {'lac': -1, 'cid': 4},
        ]

        for entry in entries:
            measure, cell = self.get_sample_measure_cell(**entry)
            self.check_normalized_cell(measure, cell, None)

    def test_mnc_above_1000_for_a_gsm_network(self):
        measure, cell = self.get_sample_measure_cell(radio='gsm', mnc=1001)
        self.check_normalized_cell(measure, cell, None)

    def test_wrong_gsm_radio_type_is_corrected_for_large_cid(self):
        measure, cell = self.get_sample_measure_cell(radio='gsm', cid=65536)
        self.check_normalized_cell(
            measure, cell, {'radio': RADIO_TYPE['umts']})

    def test_valid_umts_cid_is_32_bit(self):
        valid_cid = constants.MAX_CID_ALL
        measure, cell = self.get_sample_measure_cell(
            radio='umts', cid=valid_cid)
        self.check_normalized_cell(measure, cell, {'cid': valid_cid})

    def test_invalid_umts_cid_is_not_32_bit(self):
        invalid_cid = constants.MAX_CID_ALL + 1
        measure, cell = self.get_sample_measure_cell(
            radio='umts', cid=invalid_cid)
        self.check_normalized_cell(measure, cell, None)

    def test_valid_cdma_cid_is_16_bit(self):
        valid_cid = constants.MAX_CID_CDMA
        measure, cell = self.get_sample_measure_cell(
            radio='cdma', cid=valid_cid)
        self.check_normalized_cell(measure, cell, {'cid': valid_cid})

    def test_invalid_cdma_cid_is_not_16_bit(self):
        invalid_cid = constants.MAX_CID_CDMA + 1
        measure, cell = self.get_sample_measure_cell(
            radio='cdma', cid=invalid_cid)
        self.check_normalized_cell(measure, cell, None)

    def test_valid_lte_cid_is_28_bit(self):
        valid_cid = constants.MAX_CID_LTE
        measure, cell = self.get_sample_measure_cell(
            radio='lte', cid=valid_cid)
        self.check_normalized_cell(measure, cell, {'cid': valid_cid})

    def test_invalid_lte_cid_is_not_28_bit(self):
        invalid_cid = constants.MAX_CID_LTE + 1
        measure, cell = self.get_sample_measure_cell(
            radio='lte', cid=invalid_cid)
        self.check_normalized_cell(measure, cell, None)

    def test_valid_lac_for_gsm_umts_lte_is_less_or_equal_to_65533(self):
        valid_lac = constants.MAX_LAC_GSM_UMTS_LTE
        for radio in ('gsm', 'umts', 'lte'):
            measure, cell = self.get_sample_measure_cell(
                radio=radio, lac=valid_lac)
            self.check_normalized_cell(measure, cell, {'lac': valid_lac})

    def test_invalid_lac_for_gsm_umts_lte_is_greater_than_65533(self):
        invalid_lac = constants.MAX_LAC_GSM_UMTS_LTE + 1
        for radio in ('gsm', 'umts', 'lte'):
            measure, cell = self.get_sample_measure_cell(
                radio=radio, lac=invalid_lac)
            self.check_normalized_cell(measure, cell, None)

    def test_valid_lac_for_cdma_is_less_or_equal_to_65534(self):
        valid_lac = constants.MAX_LAC_ALL
        measure, cell = self.get_sample_measure_cell(
            radio='cdma', lac=valid_lac)
        self.check_normalized_cell(measure, cell, {'lac': valid_lac})

    def test_invalid_lac_for_cdma_is_greater_than_65534(self):
        invalid_lac = constants.MAX_LAC_ALL + 1
        measure, cell = self.get_sample_measure_cell(
            radio='cdma', lac=invalid_lac)
        self.check_normalized_cell(measure, cell, None)


class TestWifiValidation(ValidationTest):

    def check_normalized_wifi(self, measure, wifi, expect):
        return self.check_normalized(
            normalized_wifi_dict,
            measure, wifi, expect)

    def get_sample_measure_wifi(self, **kwargs):
        measure = {
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
            'signalToNoiseRatio': 37,
        }
        for (k, v) in kwargs.items():
            if k in measure:
                measure[k] = v
            else:
                wifi[k] = v
        return (measure, wifi)

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
            measure, wifi = self.get_sample_measure_wifi(key=in_)
            self.check_normalized_wifi(measure, wifi, dict(key=out))

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
            measure, wifi = self.get_sample_measure_wifi(key=key)
            self.check_normalized_wifi(measure, wifi, None)

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
            measure, wifi = self.get_sample_measure_wifi(
                frequency=f, channel=c)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

            measure, wifi = self.get_sample_measure_wifi(
                frequency=f, channel=0)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

            measure, wifi = self.get_sample_measure_wifi(
                frequency=0, channel=c)
            wifi = self.check_normalized_wifi(measure, wifi, dict(channel=c))
            self.assertFalse('frequency' in wifi)

    def test_valid_signal(self):
        valid_signals = [-200, -100, -1]

        for signal in valid_signals:
            measure, wifi = self.get_sample_measure_wifi(signal=signal)
            self.check_normalized_wifi(measure, wifi, dict(signal=signal))

    def test_invalid_signal(self):
        invalid_signals = [-300, -201, 0, 10]

        for signal in invalid_signals:
            measure, wifi = self.get_sample_measure_wifi(signal=signal)
            self.check_normalized_wifi(measure, wifi, dict(signal=0))

    def test_valid_snr(self):
        valid_snrs = [0, 12, 100]

        for snr in valid_snrs:
            measure, wifi = self.get_sample_measure_wifi(
                signalToNoiseRatio=snr)
            self.check_normalized_wifi(
                measure, wifi, dict(signalToNoiseRatio=snr))

    def test_invalid_snr(self):
        invalid_snrs = [-1, -50, 101]

        for snr in invalid_snrs:
            measure, wifi = self.get_sample_measure_wifi(
                signalToNoiseRatio=snr)
            self.check_normalized_wifi(
                measure, wifi, dict(signalToNoiseRatio=0))

    def test_valid_channel(self):
        valid_channels = [1, 20, 45, 165]

        for channel in valid_channels:
            measure, wifi = self.get_sample_measure_wifi(channel=channel)
            wifi = self.check_normalized_wifi(
                measure, wifi, dict(channel=channel))
            self.assertFalse('frequency' in wifi)

    def test_invalid_channel_is_corrected_by_valid_frequency(self):
        invalid_channels = [-10, -1, 201, 2500]

        for c in invalid_channels:
            measure, wifi = self.get_sample_measure_wifi()
            chan = wifi['channel']
            wifi['channel'] = c
            wifi = self.check_normalized_wifi(measure, wifi,
                                              dict(channel=chan))
            self.assertFalse('frequency' in wifi)

    def test_invalid_frequency_has_no_effect_and_is_dropped(self):
        invalid_frequencies = [-1, 2000, 2411, 2473, 5168, 5826, 6000]

        for frequency in invalid_frequencies:
            measure, wifi = self.get_sample_measure_wifi(frequency=frequency)
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
            self.assertEqual(normalized_time(in_), expected)
