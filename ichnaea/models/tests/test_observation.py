import simplejson

from ichnaea.models import (
    BlueObservation,
    BlueReport,
    CellObservation,
    CellReport,
    constants,
    Radio,
    Report,
    ReportSource,
    WifiObservation,
    WifiReport,
)
from ichnaea.tests.base import (
    GB_LAT,
    GB_LON,
    GB_MCC,
    TestCase,
)
from ichnaea.tests.factories import (
    BlueObservationFactory,
    CellObservationFactory,
    WifiObservationFactory
)


class BaseTest(TestCase):

    def compare(self, name, value, expect):
        self.assertEqual(self.sample(**{name: value})[name], expect)


class TestReport(BaseTest):

    def sample(self, **kwargs):
        report = {
            'lat': GB_LAT,
            'lon': GB_LON,
        }
        for (k, v) in kwargs.items():
            report[k] = v
        return Report.validate(report)

    def test_latlon(self):
        self.assertFalse(self.sample(lat=GB_LAT, lon=GB_LON) is None)
        self.assertEqual(self.sample(lat=0.0, lon=0.0), None)
        self.assertEqual(self.sample(lat=GB_LAT, lon=None), None)

    def test_accuracy(self):
        field = 'accuracy'
        self.compare(field, constants.MIN_ACCURACY - 0.1, None)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 10.2, 10.2)
        self.compare(field, constants.MAX_ACCURACY + 0.1, None)

    def test_altitude(self):
        field = 'altitude'
        self.compare(field, constants.MIN_ALTITUDE - 0.1, None)
        self.compare(field, -100.0, -100.0)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 10.1, 10.1)
        self.compare(field, constants.MAX_ALTITUDE + 0.1, None)

    def test_altitude_accuracy(self):
        field = 'altitude_accuracy'
        self.compare(field, constants.MIN_ALTITUDE_ACCURACY - 0.1, None)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 10.2, 10.2)
        self.compare(field, constants.MAX_ALTITUDE_ACCURACY + 0.1, None)

    def test_heading(self):
        field = 'heading'
        self.compare(field, constants.MIN_HEADING - 0.1, None)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 357.2, 357.2)
        self.compare(field, constants.MAX_HEADING + 0.1, None)

    def test_pressure(self):
        field = 'pressure'
        self.compare(field, constants.MIN_PRESSURE - 0.1, None)
        self.compare(field, 870.1, 870.1)
        self.compare(field, 1080.2, 1080.2)
        self.compare(field, constants.MAX_PRESSURE + 0.1, None)

    def test_source(self):
        field = 'source'
        for source in (ReportSource.fixed, ReportSource.gnss,
                       ReportSource.fused, ReportSource.query):
            self.compare(field, source, source)
        self.compare(field, 'gnss', ReportSource.gnss)

    def test_speed(self):
        field = 'speed'
        self.compare(field, constants.MIN_SPEED - 0.1, None)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 100.1, 100.1)
        self.compare(field, constants.MAX_SPEED + 0.1, None)

    def test_timestamp(self):
        field = 'timestamp'
        self.compare(field, constants.MIN_TIMESTAMP - 1, None)
        self.compare(field, 1405602028568, 1405602028568)
        self.compare(field, constants.MAX_TIMESTAMP + 1, None)


class TestBlueObservation(BaseTest):

    def test_fields(self):
        mac = '3680873e9b83'
        obs = BlueObservation.create(
            mac=mac, lat=GB_LAT, lon=GB_LON,
            pressure=1010.2, source='fixed', timestamp=1405602028568,
            signal=-45)

        self.assertEqual(obs.lat, GB_LAT)
        self.assertEqual(obs.lon, GB_LON)
        self.assertEqual(obs.mac, mac)
        self.assertEqual(obs.pressure, 1010.2)
        self.assertEqual(obs.signal, -45)
        self.assertEqual(obs.source, ReportSource.fixed)
        self.assertEqual(obs.timestamp, 1405602028568)
        self.assertEqual(obs.shard_id, '8')

    def test_json(self):
        obs = BlueObservationFactory.build(
            accuracy=None, source=ReportSource.gnss)
        result = BlueObservation.from_json(simplejson.loads(
            simplejson.dumps(obs.to_json())))
        self.assertTrue(type(result), BlueObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(result.mac, obs.mac)
        self.assertEqual(result.lat, obs.lat)
        self.assertEqual(result.lon, obs.lon)
        self.assertEqual(result.source, ReportSource.gnss)
        self.assertEqual(type(result.source), ReportSource)

    def test_weight(self):
        obs_factory = BlueObservationFactory.build
        self.assertAlmostEqual(obs_factory(
            accuracy=None, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=0.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=40.0, signal=-80).weight, 0.5)
        self.assertAlmostEqual(obs_factory(
            accuracy=100.0, signal=-80).weight, 0.316, 3)


class TestBlueReport(BaseTest):

    def sample(self, **kwargs):
        report = {'mac': '3680873e9b83'}
        for (k, v) in kwargs.items():
            report[k] = v
        return BlueReport.validate(report)

    def test_mac(self):
        self.assertFalse(self.sample(mac='3680873e9b83') is None)
        self.assertEqual(self.sample(mac=''), None)
        self.assertEqual(self.sample(mac='1234567890123'), None)
        self.assertEqual(self.sample(mac='aaaaaaZZZZZZ'), None)

    def test_age(self):
        field = 'age'
        self.compare(field, constants.MIN_AGE - 1, None)
        self.compare(field, -40000, -40000)
        self.compare(field, 60000, 60000)
        self.compare(field, constants.MAX_AGE + 1, None)

    def test_signal(self):
        field = 'signal'
        self.compare(field, constants.MIN_BLUE_SIGNAL - 1, None)
        self.compare(field, -90, -90)
        self.compare(field, -10, -10)
        self.compare(field, constants.MAX_BLUE_SIGNAL + 1, None)


class TestCellObservation(BaseTest):

    def test_fields(self):
        obs = CellObservation.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=5, lac=12345, cid=23456,
            lat=GB_LAT, lon=GB_LON,
            pressure=1010.2, source='gnss', timestamp=1405602028568,
            asu=26, signal=-61, ta=10)

        self.assertEqual(obs.lat, GB_LAT)
        self.assertEqual(obs.lon, GB_LON)
        self.assertEqual(obs.pressure, 1010.2)
        self.assertEqual(obs.source, ReportSource.gnss)
        self.assertEqual(obs.timestamp, 1405602028568)
        self.assertEqual(obs.radio, Radio.gsm)
        self.assertEqual(obs.mcc, GB_MCC)
        self.assertEqual(obs.mnc, 5)
        self.assertEqual(obs.lac, 12345)
        self.assertEqual(obs.cid, 23456)
        self.assertEqual(obs.asu, 26)
        self.assertEqual(obs.signal, -61)
        self.assertEqual(obs.ta, 10)
        self.assertEqual(obs.shard_id, 'gsm')

    def test_mcc_latlon(self):
        sample = dict(radio=Radio.gsm, mnc=6, lac=1, cid=2,
                      lat=GB_LAT, lon=GB_LON)
        self.assertFalse(CellObservation.create(mcc=GB_MCC, **sample) is None)
        self.assertTrue(CellObservation.create(mcc=262, **sample) is None)

    def test_json(self):
        obs = CellObservationFactory.build(
            accuracy=None, source='fixed')
        result = CellObservation.from_json(simplejson.loads(
            simplejson.dumps(obs.to_json())))
        self.assertTrue(type(result), CellObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(type(result.radio), Radio)
        self.assertEqual(result.radio, obs.radio)
        self.assertEqual(result.mcc, obs.mcc)
        self.assertEqual(result.mnc, obs.mnc)
        self.assertEqual(result.lac, obs.lac)
        self.assertEqual(result.cid, obs.cid)
        self.assertEqual(result.lat, obs.lat)
        self.assertEqual(result.lon, obs.lon)
        self.assertEqual(result.source, ReportSource.fixed)
        self.assertEqual(type(result.source), ReportSource)

    def test_weight(self):
        obs_factory = CellObservationFactory.build
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=None, signal=-95).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=0.0, signal=-95).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=10.0, signal=-95).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=160.0, signal=-95).weight, 0.25, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=200.0, signal=-95).weight, 0.22, 2)

        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=10.0, signal=-51).weight, 10.17, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=160.0, signal=-51).weight, 2.54, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=10.0, signal=-113).weight, 0.52, 2)

        self.assertAlmostEqual(obs_factory(
            radio=Radio.wcdma, accuracy=10.0, signal=-25).weight, 256.0, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.wcdma, accuracy=160.0, signal=-25).weight, 64.0, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.wcdma, accuracy=10.0, signal=-121).weight, 0.47, 2)

        self.assertAlmostEqual(obs_factory(
            radio=Radio.lte, accuracy=10.0, signal=-43).weight, 47.96, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.lte, accuracy=160.0, signal=-43).weight, 11.99, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.lte, accuracy=10.0, signal=-140).weight, 0.3, 2)


class TestCellReport(BaseTest):

    def sample(self, **kwargs):
        report = {
            'radio': Radio.gsm,
            'mcc': GB_MCC,
            'mnc': 1,
            'lac': 2,
            'cid': 3,
        }
        for (k, v) in kwargs.items():
            report[k] = v
        return CellReport.validate(report)

    def test_cellid(self):
        self.assertFalse(self.sample() is None)
        self.assertEqual(self.sample(radio=None), None)
        self.assertEqual(self.sample(mcc=None), None)
        self.assertEqual(self.sample(mnc=None), None)
        self.assertEqual(self.sample(lac=None), None)
        self.assertEqual(self.sample(cid=None), None)

    def test_radio(self):
        field = 'radio'
        self.compare(field, 'gsm', Radio.gsm)
        self.compare(field, 'umts', Radio.wcdma)
        self.compare(field, 'wcdma', Radio.wcdma)
        self.compare(field, 'lte', Radio.lte)
        self.assertEqual(self.sample(radio='cdma'), None)
        self.assertEqual(self.sample(radio='hspa'), None)
        self.assertEqual(self.sample(radio='wimax'), None)

    def test_mcc(self):
        self.compare('mcc', 262, 262)
        self.assertEqual(self.sample(mcc=constants.MIN_MCC - 1), None)
        self.assertEqual(self.sample(mcc=constants.MAX_MCC + 1), None)

    def test_mnc(self):
        self.compare('mnc', 5, 5)
        self.assertEqual(self.sample(mnc=constants.MIN_MNC - 1), None)
        self.assertEqual(self.sample(mnc=constants.MAX_MNC + 1), None)

    def test_lac(self):
        self.compare('lac', 5, 5)
        self.assertEqual(self.sample(lac=constants.MIN_LAC - 1), None)
        self.assertEqual(self.sample(lac=constants.MAX_LAC + 1), None)

    def test_lac_cid(self):
        self.assertEqual(self.sample(
            radio=Radio.gsm, lac=None,
            cid=constants.MAX_CID_GSM, psc=None), None)
        self.assertEqual(self.sample(
            radio=Radio.gsm, lac=None,
            cid=constants.MAX_CID_GSM, psc=1), None)

    def test_cid(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            self.assertEqual(self.sample(
                radio=radio, cid=constants.MIN_CID - 1), None)
            self.assertEqual(self.sample(
                radio=radio, cid=12345)['cid'], 12345)
            self.assertEqual(self.sample(
                radio=radio, cid=constants.MAX_CID + 1), None)

        # correct radio type for large GSM cid
        cid = constants.MAX_CID_GSM + 1
        self.assertEqual(self.sample(
            radio=Radio.gsm, cid=cid)['radio'], Radio.wcdma)
        # accept large WCDMA/LTE cid
        self.assertEqual(self.sample(
            radio=Radio.wcdma, cid=cid)['cid'], cid)
        self.assertEqual(self.sample(
            radio=Radio.lte, cid=cid)['cid'], cid)

    def test_psc(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            self.assertEqual(self.sample(
                radio=radio, psc=constants.MIN_PSC - 1)['psc'], None)
            self.assertEqual(self.sample(
                radio=radio, psc=15)['psc'], 15)
            self.assertEqual(self.sample(
                radio=radio, cid=constants.MAX_PSC + 1)['psc'], None)

        self.assertEqual(self.sample(
            radio=Radio.lte, psc=constants.MAX_PSC_LTE + 1)['psc'], None)

    def test_age(self):
        field = 'age'
        self.compare(field, constants.MIN_AGE - 1, None)
        self.compare(field, -40000, -40000)
        self.compare(field, 60000, 60000)
        self.compare(field, constants.MAX_AGE + 1, None)

    def test_asu(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            self.assertEqual(self.sample(
                radio=radio,
                asu=constants.MIN_CELL_ASU[radio] - 1)['asu'], None)
            self.assertEqual(self.sample(
                radio=radio, asu=15)['asu'], 15)
            self.assertEqual(self.sample(
                radio=radio,
                asu=constants.MAX_CELL_ASU[radio] + 1)['asu'], None)

    def test_asu_signal(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            # if both are specified, leave them untouched
            self.assertEqual(self.sample(
                radio=radio, asu=15, signal=-75)['signal'], -75)

        for radio, signal in ((Radio.gsm, -83),
                              (Radio.wcdma, -101),
                              (Radio.lte, -125)):
            # calculate signal from asu
            self.assertEqual(self.sample(
                radio=radio, asu=15, signal=None)['signal'], signal)
            # switch asu/signal fields
            self.assertEqual(self.sample(
                radio=radio, asu=signal, signal=None)['signal'], signal)
            self.assertEqual(self.sample(
                radio=radio, asu=signal, signal=10)['signal'], signal)

    def test_signal(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            self.assertEqual(self.sample(
                radio=radio,
                signal=constants.MIN_CELL_SIGNAL[radio] - 1)['signal'], None)
            self.assertEqual(self.sample(
                radio=radio, signal=-75)['signal'], -75)
            self.assertEqual(self.sample(
                radio=radio,
                signal=constants.MAX_CELL_SIGNAL[radio] + 1)['signal'], None)

    def test_ta(self):
        field = 'ta'
        self.compare(field, constants.MIN_CELL_TA - 1, None)
        self.compare(field, 0, 0)
        self.compare(field, 31, 31)
        self.compare(field, constants.MAX_CELL_TA + 1, None)

        self.assertEqual(self.sample(radio=Radio.gsm, ta=1)['ta'], 1)
        self.assertEqual(self.sample(radio=Radio.wcdma, ta=1)['ta'], None)
        self.assertEqual(self.sample(radio=Radio.lte, ta=1)['ta'], 1)


class TestWifiObservation(BaseTest):

    def test_invalid(self):
        self.assertTrue(WifiObservation.create(
            mac='3680873e9b83', lat=0.0, lon=0.0) is None)
        self.assertTrue(WifiObservation.create(
            mac='', lat=0.0, lon=0.0) is None)

    def test_fields(self):
        mac = '3680873e9b83'
        obs = WifiObservation.create(
            mac=mac, lat=GB_LAT, lon=GB_LON,
            pressure=1010.2, source=ReportSource.query,
            timestamp=1405602028568,
            channel=5, signal=-45)

        self.assertEqual(obs.lat, GB_LAT)
        self.assertEqual(obs.lon, GB_LON)
        self.assertEqual(obs.mac, mac)
        self.assertEqual(obs.pressure, 1010.2)
        self.assertEqual(obs.source, ReportSource.query)
        self.assertEqual(obs.timestamp, 1405602028568)
        self.assertEqual(obs.channel, 5)
        self.assertEqual(obs.signal, -45)
        self.assertEqual(obs.shard_id, '8')

    def test_json(self):
        obs = WifiObservationFactory.build(
            accuracy=None, source=ReportSource.query)
        result = WifiObservation.from_json(simplejson.loads(
            simplejson.dumps(obs.to_json())))
        self.assertTrue(type(result), WifiObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(result.mac, obs.mac)
        self.assertEqual(result.lat, obs.lat)
        self.assertEqual(result.lon, obs.lon)
        self.assertEqual(result.source, ReportSource.query)
        self.assertEqual(type(result.source), ReportSource)

    def test_weight(self):
        obs_factory = WifiObservationFactory.build
        self.assertAlmostEqual(obs_factory(
            accuracy=None, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=0.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=40.0, signal=-80).weight, 0.5)
        self.assertAlmostEqual(obs_factory(
            accuracy=100.0, signal=-80).weight, 0.316, 3)

        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-100).weight, 0.482, 3)
        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-30).weight, 16.0, 2)
        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-10).weight, 123.46, 2)

        self.assertAlmostEqual(obs_factory(
            accuracy=40.0, signal=-30).weight, 8.0, 2)
        self.assertAlmostEqual(obs_factory(
            accuracy=100.0, signal=-30).weight, 5.06, 2)
        self.assertAlmostEqual(obs_factory(
            accuracy=100.0, signal=-10).weight, 39.04, 2)


class TestWifiReport(BaseTest):

    def sample(self, **kwargs):
        report = {'mac': '3680873e9b83'}
        for (k, v) in kwargs.items():
            report[k] = v
        return WifiReport.validate(report)

    def test_mac(self):
        self.assertFalse(self.sample(mac='3680873e9b83') is None)
        self.assertFalse(self.sample(mac='3680873E9B83') is None)
        self.assertFalse(self.sample(mac='36:80:87:3e:9b:83') is None)
        self.assertFalse(self.sample(mac='36-80-87-3e-9b-83') is None)
        self.assertFalse(self.sample(mac='36.80.87.3e.9b.83') is None)
        # We considered but do not ban locally administered WiFi
        # mac addresses based on the U/L bit
        # https://en.wikipedia.org/wiki/MAC_address
        self.assertFalse(self.sample(mac='0a0000000000') is None)

        self.assertEqual(self.sample(mac=''), None)
        self.assertEqual(self.sample(mac='1234567890123'), None)
        self.assertEqual(self.sample(mac='aaaaaaZZZZZZ'), None)
        self.assertEqual(self.sample(mac='000000000000'), None)
        self.assertEqual(self.sample(mac='ffffffffffff'), None)
        self.assertEqual(self.sample(mac=constants.WIFI_TEST_MAC), None)

    def test_age(self):
        field = 'age'
        self.compare(field, constants.MIN_AGE - 1, None)
        self.compare(field, -40000, -40000)
        self.compare(field, 60000, 60000)
        self.compare(field, constants.MAX_AGE + 1, None)

    def test_channel(self):
        field = 'channel'
        self.compare(field, constants.MIN_WIFI_CHANNEL - 1, None)
        self.compare(field, 1, 1)
        self.compare(field, 36, 36)
        self.compare(field, constants.MAX_WIFI_CHANNEL + 1, None)

    def test_channel_frequency(self):
        self.assertEqual(self.sample(channel=0, frequency=10)['channel'], None)
        self.assertEqual(self.sample(channel=0, frequency=2427)['channel'], 4)
        self.assertEqual(self.sample(channel=1, frequency=2000)['channel'], 1)
        self.assertEqual(self.sample(channel=1, frequency=2427)['channel'], 1)

    def test_frequency(self):
        self.assertEqual(self.sample(frequency=2411)['channel'], None)
        self.assertEqual(self.sample(frequency=2412)['channel'], 1)
        self.assertEqual(self.sample(frequency=2484)['channel'], 14)
        self.assertEqual(self.sample(frequency=2473)['channel'], None)
        self.assertEqual(self.sample(frequency=5168)['channel'], None)
        self.assertEqual(self.sample(frequency=5170)['channel'], 34)
        self.assertEqual(self.sample(frequency=5825)['channel'], 165)
        self.assertEqual(self.sample(frequency=5826)['channel'], None)

    def test_signal(self):
        field = 'signal'
        self.compare(field, constants.MIN_WIFI_SIGNAL - 1, None)
        self.compare(field, -90, -90)
        self.compare(field, -10, -10)
        self.compare(field, constants.MAX_WIFI_SIGNAL + 1, None)

    def test_snr(self):
        field = 'snr'
        self.compare(field, constants.MIN_WIFI_SNR - 1, None)
        self.compare(field, 1, 1)
        self.compare(field, 40, 40)
        self.compare(field, constants.MAX_WIFI_SNR + 1, None)
