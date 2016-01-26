from ichnaea.models import (
    Radio,
    BlueObservation,
    CellObservation,
    WifiObservation,
)
from ichnaea.models import constants
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


class TestBlue(ValidationTest):

    def check_normalized_blue(self, obs, blue, expect):
        return self.check_normalized(
            BlueObservation.validate,
            obs, blue, expect)

    def get_sample(self, **kwargs):
        obs = {
            'accuracy': constants.MAX_ACCURACY_BLUE,
            'altitude': 220.1,
            'altitude_accuracy': 10.0,
            'lat': 49.25,
            'lon': 123.10,
            'time': self.time,
        }
        blue = {
            'key': '12:34:56:78:90:12',
            'signal': -85,
        }
        for (k, v) in kwargs.items():
            if k in obs:
                obs[k] = v
            else:
                blue[k] = v
        return (obs, blue)

    def test_valid_accuracy(self):
        for accuracy in [0.0, 1.6, 10.1, constants.MAX_ACCURACY_BLUE]:
            obs, blue = self.get_sample(accuracy=accuracy)
            self.check_normalized_blue(obs, blue, {'accuracy': accuracy})

    def test_invalid_accuracy(self):
        for accuracy in [-10.0, -1.2]:
            obs, blue = self.get_sample(accuracy=accuracy)
            self.check_normalized_blue(obs, blue, {'accuracy': None})

        obs, blue = self.get_sample(accuracy=constants.MAX_ACCURACY_BLUE + 0.1)
        self.check_normalized_blue(obs, blue, None)


class TestCell(ValidationTest):

    def setUp(self):
        super(TestCell, self).setUp()
        self.invalid_lacs = [constants.MIN_LAC - 1, constants.MAX_LAC + 1]
        self.invalid_cids = [constants.MIN_CID - 1, constants.MAX_CID + 1]

        self.valid_pscs = [constants.MIN_PSC, constants.MAX_PSC_LTE]
        self.invalid_pscs = [constants.MIN_PSC - 1, constants.MAX_PSC + 1]

    def check_normalized_cell(self, observation, cell, expect):
        return self.check_normalized(
            CellObservation.validate,
            observation, cell, expect)

    def get_sample(self, **kwargs):
        obs = {
            'accuracy': constants.MAX_ACCURACY_CELL,
            'altitude': 220.0,
            'altitude_accuracy': 10.0,
            'lat': PARIS_LAT,
            'lon': PARIS_LON,
            'radio': Radio.gsm.name,
            'time': self.time,
            'report_id': None,
        }
        cell = {
            'cid': 34567,
            'lac': 12345,
            'mcc': FRANCE_MCC,
            'mnc': VIVENDI_MNC,
            'psc': None,
        }
        for (k, v) in kwargs.items():
            if k in obs:
                obs[k] = v
            else:
                cell[k] = v
        return (obs, cell)

    def test_radio_values(self):
        radio_pairs = [
            ('gsm', {'radio': Radio.gsm}),
            (Radio.gsm.name, {'radio': Radio.gsm}),
            ('cdma', None),
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

    def test_cdma_cell(self):
        obs, cell = self.get_sample(
            radio=Radio.cdma.name, mcc=310, mnc=542, lac=3, cid=4)
        self.check_normalized_cell(obs, cell, None)

    def test_lat_lon_mcc_mnc_groups(self):
        valid_lat_lon_mcc_triples = [
            (FREMONT_LAT, FREMONT_LON, USA_MCC),
            (SAO_PAULO_LAT, SAO_PAULO_LON, BRAZIL_MCC),
            (PARIS_LAT, PARIS_LON, FRANCE_MCC),
        ]
        for (lat, lon, mcc) in valid_lat_lon_mcc_triples:
            for mnc in (0, 542, 999):
                obs, cell = self.get_sample(
                    lat=lat, lon=lon, mcc=mcc, mnc=mnc)
                self.check_normalized_cell(
                    obs, cell, dict(lat=lat, lon=lon, mcc=mcc, mnc=mnc))

    def test_outside_of_region_lat_lon(self):
        obs, cell = self.get_sample(
            mcc=USA_MCC, lat=PARIS_LAT, lon=PARIS_LON)
        self.check_normalized_cell(obs, cell, None)

    def test_invalid_mcc(self):
        for mcc in [-10, -1, 0, 101, 1000, 3456]:
            obs, cell = self.get_sample(mcc=mcc)
            self.check_normalized_cell(obs, cell, None)

    def test_invalid_mnc(self):
        for mnc in [-10, -1, 1000, 3456]:
            obs, cell = self.get_sample(mnc=mnc)
            self.check_normalized_cell(obs, cell, None)

    def test_valid_lac_cid_invalid_psc(self):
        for lac in [constants.MIN_LAC, constants.MAX_LAC]:
            for cid in [constants.MIN_CID, constants.MAX_CID]:
                for psc in self.invalid_pscs:
                    obs, cell = self.get_sample(
                        lac=lac, cid=cid, psc=psc)
                    self.check_normalized_cell(
                        obs, cell, dict(lac=lac, cid=cid, psc=None))

    def test_invalid_lac_invalid_psc(self):
        for lac in self.invalid_lacs:
            for psc in self.invalid_pscs:
                obs, cell = self.get_sample(lac=lac, psc=psc)
                self.check_normalized_cell(obs, cell, None)

    def test_invalid_lac_valid_psc(self):
        for lac in self.invalid_lacs:
            for psc in self.valid_pscs:
                obs, cell = self.get_sample(lac=lac, psc=psc)
                self.check_normalized_cell(obs, cell, None)

    def test_invalid_cid_and_psc(self):
        for cid in self.invalid_cids:
            for psc in self.invalid_pscs:
                obs, cell = self.get_sample(cid=cid, psc=psc)
                self.check_normalized_cell(obs, cell, None)

    def test_invalid_cid_valid_psc(self):
        for cid in self.invalid_cids:
            for psc in self.valid_pscs:
                obs, cell = self.get_sample(cid=cid, psc=psc)
                self.check_normalized_cell(obs, cell, None)

    def test_invalid_latitude(self):
        for lat in [constants.MIN_LAT - 0.1, constants.MAX_LAT + 0.1]:
            obs, cell = self.get_sample(lat=lat)
            self.check_normalized_cell(obs, cell, None)

    def test_invalid_longitude(self):
        for lon in [constants.MIN_LON - 0.1, constants.MAX_LON + 0.1]:
            obs, cell = self.get_sample(lon=lon)
            self.check_normalized_cell(obs, cell, None)

    def test_valid_accuracy(self):
        for accuracy in [0.0, 1.6, 10.1, constants.MAX_ACCURACY_CELL]:
            obs, cell = self.get_sample(accuracy=accuracy)
            self.check_normalized_cell(obs, cell, {'accuracy': accuracy})

    def test_valid_altitude(self):
        for altitude in [-100.0, -1.6, 0.0, 10.1, 100.0]:
            obs, cell = self.get_sample(altitude=altitude)
            self.check_normalized_cell(obs, cell, {'altitude': altitude})

    def test_valid_altitude_accuracy(self):
        for altitude_accuracy in [0.0, 1.6, 100.1, 1000.0]:
            obs, cell = self.get_sample(
                altitude_accuracy=altitude_accuracy)
            self.check_normalized_cell(
                obs, cell, {'altitude_accuracy': altitude_accuracy})

    def test_invalid_accuracy(self):
        for accuracy in [-10.0, -1.2]:
            obs, cell = self.get_sample(accuracy=accuracy)
            self.check_normalized_cell(obs, cell, {'accuracy': None})

        obs, cell = self.get_sample(accuracy=constants.MAX_ACCURACY_CELL + 0.1)
        self.check_normalized_cell(obs, cell, None)

    def test_invalid_altitude(self):
        for altitude in [-20000.0, 200000.0]:
            obs, cell = self.get_sample(altitude=altitude)
            self.check_normalized_cell(obs, cell, {'altitude': None})

    def test_invalid_altitude_accuracy(self):
        for altitude_accuracy in [-10.0, -1.2, 500000.0]:
            obs, cell = self.get_sample(
                altitude_accuracy=altitude_accuracy)
            self.check_normalized_cell(
                obs, cell, {'altitude_accuracy': None})

    def test_valid_ta(self):
        for ta in (constants.MIN_CELL_TA, 15, constants.MAX_CELL_TA):
            for radio in (Radio.gsm, Radio.lte):
                obs, cell = self.get_sample(radio=radio.name, ta=ta)
                self.check_normalized_cell(obs, cell, {'ta': ta})

    def test_invalid_ta(self):
        for ta in (constants.MIN_CELL_TA - 1, constants.MAX_CELL_TA + 1):
            for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
                obs, cell = self.get_sample(radio=radio.name, ta=ta)
                self.check_normalized_cell(obs, cell, {'ta': None})

        for ta in (constants.MIN_CELL_TA, 15, constants.MAX_CELL_TA):
            obs, cell = self.get_sample(radio=Radio.wcdma.name, ta=ta)
            self.check_normalized_cell(obs, cell, {'ta': None})

    def test_valid_asu(self):
        for asu in (0, 10, 31):
            obs, cell = self.get_sample(radio=Radio.gsm.name, asu=asu)
            self.check_normalized_cell(obs, cell, {'asu': asu})

        for asu in (-5, 0, 10, 91):
            obs, cell = self.get_sample(radio=Radio.wcdma.name, asu=asu)
            self.check_normalized_cell(obs, cell, {'asu': asu})

        for asu in (0, 10, 97):
            obs, cell = self.get_sample(radio=Radio.lte.name, asu=asu)
            self.check_normalized_cell(obs, cell, {'asu': asu})

    def test_invalid_asu(self):
        for asu in (-5, -1, 32, 255):
            obs, cell = self.get_sample(radio=Radio.gsm.name, asu=asu)
            self.check_normalized_cell(obs, cell, {'asu': None})

        for asu in (-10, -6, 92, 99, 255):
            obs, cell = self.get_sample(radio=Radio.wcdma.name, asu=asu)
            self.check_normalized_cell(obs, cell, {'asu': None})

        for asu in (-5, -1, 98, 99, 255):
            obs, cell = self.get_sample(radio=Radio.lte.name, asu=asu)
            self.check_normalized_cell(obs, cell, {'asu': None})

    def test_valid_signal(self):
        for signal in (-113, -100, -51):
            obs, cell = self.get_sample(radio=Radio.gsm.name, signal=signal)
            self.check_normalized_cell(obs, cell, {'signal': signal})

        for signal in (-121, -100, -25):
            obs, cell = self.get_sample(radio=Radio.wcdma.name, signal=signal)
            self.check_normalized_cell(obs, cell, {'signal': signal})

        for signal in (-140, -100, -43):
            obs, cell = self.get_sample(radio=Radio.lte.name, signal=signal)
            self.check_normalized_cell(obs, cell, {'signal': signal})

    def test_invalid_signal(self):
        for signal in (-114, -50, 0, 10):
            obs, cell = self.get_sample(radio=Radio.gsm.name, signal=signal)
            self.check_normalized_cell(obs, cell, {'signal': None})

        for signal in (-122, -24, 0, 10):
            obs, cell = self.get_sample(radio=Radio.wcdma.name, signal=signal)
            self.check_normalized_cell(obs, cell, {'signal': None})

        for signal in (-141, -42, 0, 10):
            obs, cell = self.get_sample(radio=Radio.lte.name, signal=signal)
            self.check_normalized_cell(obs, cell, {'signal': None})

    def test_asu_signal_field_mix(self):
        obs, cell = self.get_sample(asu=-75, signal=0)
        self.check_normalized_cell(obs, cell, {'signal': -75})

    def test_asu_signal_conversion(self):
        for asu, signal in ((-1, None), (0, -113), (16, -81),
                            (31, -51), (32, None)):
            obs, cell = self.get_sample(
                radio=Radio.gsm.name, asu=asu, signal=None)
            self.check_normalized_cell(obs, cell, {'signal': signal})

        for asu, signal in ((-6, None), (-5, -121), (0, -116),
                            (16, -100), (91, -25), (92, None)):
            obs, cell = self.get_sample(
                radio=Radio.wcdma.name, asu=asu, signal=None)
            self.check_normalized_cell(obs, cell, {'signal': signal})

        for asu, signal in ((-1, None), (0, -140), (40, -100),
                            (97, -43), (98, None)):
            obs, cell = self.get_sample(
                radio=Radio.lte.name, asu=asu, signal=None)
            self.check_normalized_cell(obs, cell, {'signal': signal})

    def test_cid_65535_invalid_lac(self):
        obs, cell = self.get_sample(lac=None, cid=65535, psc=1)
        self.check_normalized_cell(obs, cell, None)

    def test_unknown_lac_cid_65535_missing_psc(self):
        obs, cell = self.get_sample(lac=None, cid=65535, psc=None)
        self.check_normalized_cell(obs, cell, None)

    def test_lac_or_cid_and_psc(self):
        entries = [
            {'lac': None, 'cid': None},
            {'lac': 3, 'cid': None},
            {'lac': None, 'cid': 4},
        ]
        for entry in entries:
            obs, cell = self.get_sample(**entry)
            self.check_normalized_cell(obs, cell, None)

    def test_wrong_gsm_radio_type_large_cid(self):
        obs, cell = self.get_sample(radio=Radio.gsm.name, cid=65536)
        self.check_normalized_cell(
            obs, cell, {'radio': Radio.wcdma})

    def test_valid_wcdma_cid(self):
        obs, cell = self.get_sample(
            radio=Radio.wcdma.name, cid=constants.MAX_CID)
        self.check_normalized_cell(obs, cell, {'cid': constants.MAX_CID})

    def test_invalid_wcdma_cid(self):
        obs, cell = self.get_sample(
            radio=Radio.wcdma.name, cid=constants.MAX_CID + 1)
        self.check_normalized_cell(obs, cell, None)

    def test_valid_lte_cid(self):
        obs, cell = self.get_sample(
            radio=Radio.lte.name, cid=constants.MAX_CID)
        self.check_normalized_cell(obs, cell, {'cid': constants.MAX_CID})

    def test_invalid_lte_cid(self):
        obs, cell = self.get_sample(
            radio=Radio.lte.name, cid=constants.MAX_CID + 1)
        self.check_normalized_cell(obs, cell, None)

    def test_invalid_lte_psc(self):
        obs, cell = self.get_sample(
            radio=Radio.lte.name, psc=constants.MAX_PSC_LTE + 1)
        self.check_normalized_cell(obs, cell, None)


class TestWifi(ValidationTest):

    def check_normalized_wifi(self, obs, wifi, expect):
        return self.check_normalized(
            WifiObservation.validate,
            obs, wifi, expect)

    def get_sample(self, **kwargs):
        obs = {
            'accuracy': constants.MAX_ACCURACY_WIFI,
            'altitude': 220.1,
            'altitude_accuracy': 10.0,
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
            # We considered but do not ban locally administered WiFi
            # mac addresses based on the U/L bit
            # https://en.wikipedia.org/wiki/MAC_address
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
        ] + [constants.WIFI_TEST_MAC] + [
            c.join([str.format('{x:02x}', x=x)
                    for x in range(6)])
            for c in '!@#$%^&*()_+={}\x01\x02\x03\r\n']

        for key in invalid_keys:
            obs, wifi = self.get_sample(key=key)
            self.check_normalized_wifi(obs, wifi, None)

    def test_valid_accuracy(self):
        for accuracy in [0.0, 1.6, 10.1, constants.MAX_ACCURACY_WIFI]:
            obs, wifi = self.get_sample(accuracy=accuracy)
            self.check_normalized_wifi(obs, wifi, {'accuracy': accuracy})

    def test_invalid_accuracy(self):
        for accuracy in [-10.0, -1.2]:
            obs, wifi = self.get_sample(accuracy=accuracy)
            self.check_normalized_wifi(obs, wifi, {'accuracy': None})

        obs, wifi = self.get_sample(accuracy=constants.MAX_ACCURACY_WIFI + 0.1)
        self.check_normalized_wifi(obs, wifi, None)

    def test_valid_frequency_channel(self):
        valid_frequency_channels = [
            (2412, 1),
            (2427, 4),
            (2472, 13),
            (2484, 14),
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
        for signal in (constants.MIN_WIFI_SIGNAL, constants.MAX_WIFI_SIGNAL):
            obs, wifi = self.get_sample(signal=signal)
            self.check_normalized_wifi(obs, wifi, dict(signal=signal))

    def test_invalid_signal(self):
        for signal in (constants.MIN_WIFI_SIGNAL - 1,
                       constants.MAX_WIFI_SIGNAL + 1):
            obs, wifi = self.get_sample(signal=signal)
            self.check_normalized_wifi(obs, wifi, dict(signal=None))

    def test_valid_snr(self):
        for snr in [0, 12, 100]:
            obs, wifi = self.get_sample(snr=snr)
            self.check_normalized_wifi(obs, wifi, dict(snr=snr))

    def test_invalid_snr(self):
        for snr in [-1, -50, 101]:
            obs, wifi = self.get_sample(snr=snr)
            self.check_normalized_wifi(obs, wifi, dict(snr=None))

    def test_valid_channel(self):
        for channel in [1, 20, 45, 165]:
            obs, wifi = self.get_sample(channel=channel)
            wifi = self.check_normalized_wifi(
                obs, wifi, dict(channel=channel))
            self.assertFalse('frequency' in wifi)

    def test_invalid_channel_valid_frequency(self):
        for channel in [-10, -1, 201, 2500]:
            obs, wifi = self.get_sample()
            chan = wifi['channel']
            wifi['channel'] = channel
            wifi = self.check_normalized_wifi(obs, wifi,
                                              dict(channel=chan))
            self.assertFalse('frequency' in wifi)

    def test_invalid_frequency(self):
        for frequency in [-1, 2000, 2411, 2473, 5168, 5826, 6000]:
            obs, wifi = self.get_sample(frequency=frequency)
            chan = wifi['channel']
            wifi = self.check_normalized_wifi(obs, wifi,
                                              dict(channel=chan))
            self.assertFalse('frequency' in wifi)
