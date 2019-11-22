import json

from ichnaea.conftest import GB_LAT, GB_LON, GB_MCC
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
from ichnaea.tests.factories import (
    BlueObservationFactory,
    CellObservationFactory,
    WifiObservationFactory,
)


class BaseTest(object):
    def compare(self, name, value, expect):
        assert self.sample(**{name: value})[name] == expect


class TestReport(BaseTest):
    def sample(self, **kwargs):
        report = {"lat": GB_LAT, "lon": GB_LON}
        for (k, v) in kwargs.items():
            report[k] = v
        return Report.validate(report)

    def test_latlon(self):
        assert self.sample(lat=GB_LAT, lon=GB_LON) is not None
        assert self.sample(lat=0.0, lon=0.0) is None
        assert self.sample(lat=GB_LAT, lon=None) is None

    def test_accuracy(self):
        field = "accuracy"
        self.compare(field, constants.MIN_ACCURACY - 0.1, None)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 10.2, 10.2)
        self.compare(field, constants.MAX_ACCURACY + 0.1, None)

    def test_altitude(self):
        field = "altitude"
        self.compare(field, constants.MIN_ALTITUDE - 0.1, None)
        self.compare(field, -100.0, -100.0)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 10.1, 10.1)
        self.compare(field, constants.MAX_ALTITUDE + 0.1, None)

    def test_altitude_accuracy(self):
        field = "altitude_accuracy"
        self.compare(field, constants.MIN_ALTITUDE_ACCURACY - 0.1, None)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 10.2, 10.2)
        self.compare(field, constants.MAX_ALTITUDE_ACCURACY + 0.1, None)

    def test_heading(self):
        field = "heading"
        self.compare(field, constants.MIN_HEADING - 0.1, None)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 357.2, 357.2)
        self.compare(field, constants.MAX_HEADING + 0.1, None)

    def test_pressure(self):
        field = "pressure"
        self.compare(field, constants.MIN_PRESSURE - 0.1, None)
        self.compare(field, 870.1, 870.1)
        self.compare(field, 1080.2, 1080.2)
        self.compare(field, constants.MAX_PRESSURE + 0.1, None)

    def test_source(self):
        field = "source"
        for source in (
            ReportSource.fixed,
            ReportSource.gnss,
            ReportSource.fused,
            ReportSource.query,
        ):
            self.compare(field, source, source)
        self.compare(field, "gnss", ReportSource.gnss)

    def test_speed(self):
        field = "speed"
        self.compare(field, constants.MIN_SPEED - 0.1, None)
        self.compare(field, 0.0, 0.0)
        self.compare(field, 100.1, 100.1)
        self.compare(field, constants.MAX_SPEED + 0.1, None)

    def test_timestamp(self):
        field = "timestamp"
        self.compare(field, constants.MIN_TIMESTAMP - 1, None)
        self.compare(field, 1405602028568, 1405602028568)
        self.compare(field, constants.MAX_TIMESTAMP + 1, None)


class TestBlueObservation(BaseTest):
    def test_fields(self):
        mac = "3680873e9b83"
        obs = BlueObservation.create(
            mac=mac,
            lat=GB_LAT,
            lon=GB_LON,
            pressure=1010.2,
            source="fixed",
            timestamp=1405602028568,
            signal=-45,
        )

        assert obs.lat == GB_LAT
        assert obs.lon == GB_LON
        assert obs.mac == mac
        assert obs.pressure == 1010.2
        assert obs.signal == -45
        assert obs.source is ReportSource.fixed
        assert obs.timestamp == 1405602028568
        assert obs.shard_id == "8"

    def test_json(self):
        obs = BlueObservationFactory.build(accuracy=None, source=ReportSource.gnss)
        result = BlueObservation.from_json(json.loads(json.dumps(obs.to_json())))
        assert type(result) is BlueObservation
        assert result.accuracy is None
        assert result.mac == obs.mac
        assert result.lat == obs.lat
        assert result.lon == obs.lon
        assert result.source is ReportSource.gnss
        assert type(result.source) is ReportSource

    def test_weight(self):
        obs_factory = BlueObservationFactory.build
        assert round(obs_factory(accuracy=None).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0.0).weight, 2) == 1.0
        assert round(obs_factory(accuracy=10.0).weight, 2) == 1.0
        assert round(obs_factory(accuracy=40.0).weight, 2) == 0.5
        assert round(obs_factory(accuracy=100.0).weight, 2) == 0.32
        assert round(obs_factory(accuracy=100.1).weight, 2) == 0.0

        assert round(obs_factory(accuracy=None, age=1000).weight, 2) == 1.0
        assert round(obs_factory(accuracy=None, age=8000).weight, 2) == 0.5
        assert round(obs_factory(accuracy=None, age=20001).weight, 2) == 0.0

        assert round(obs_factory(accuracy=None, speed=None).weight, 2) == 1.0
        assert round(obs_factory(accuracy=None, speed=0.0).weight, 2) == 1.0
        assert round(obs_factory(accuracy=None, speed=1.0).weight, 2) == 1.0
        assert round(obs_factory(accuracy=None, speed=20.0).weight, 2) == 0.5
        assert round(obs_factory(accuracy=None, speed=51.0).weight, 2) == 0.0


class TestBlueReport(BaseTest):
    def sample(self, **kwargs):
        report = {"mac": "3680873e9b83"}
        for (k, v) in kwargs.items():
            report[k] = v
        return BlueReport.validate(report)

    def test_mac(self):
        assert self.sample(mac="3680873e9b83") is not None
        assert self.sample(mac="") is None
        assert self.sample(mac="1234567890123") is None
        assert self.sample(mac="aaaaaaZZZZZZ") is None

    def test_age(self):
        field = "age"
        self.compare(field, constants.MIN_AGE - 1, None)
        self.compare(field, -40000, -40000)
        self.compare(field, 60000, 60000)
        self.compare(field, constants.MAX_AGE + 1, None)

    def test_signal(self):
        field = "signal"
        self.compare(field, constants.MIN_BLUE_SIGNAL - 1, None)
        self.compare(field, -90, -90)
        self.compare(field, -10, -10)
        self.compare(field, constants.MAX_BLUE_SIGNAL + 1, None)


class TestCellObservation(BaseTest):
    def test_fields(self):
        obs = CellObservation.create(
            radio=Radio.gsm,
            mcc=GB_MCC,
            mnc=5,
            lac=12345,
            cid=23456,
            lat=GB_LAT,
            lon=GB_LON,
            pressure=1010.2,
            source="gnss",
            timestamp=1405602028568,
            asu=26,
            signal=-61,
            ta=10,
        )

        assert obs.lat == GB_LAT
        assert obs.lon == GB_LON
        assert obs.pressure == 1010.2
        assert obs.source == ReportSource.gnss
        assert obs.timestamp == 1405602028568
        assert obs.radio == Radio.gsm
        assert obs.mcc == GB_MCC
        assert obs.mnc == 5
        assert obs.lac == 12345
        assert obs.cid == 23456
        assert obs.asu == 26
        assert obs.signal == -61
        assert obs.ta == 10
        assert obs.shard_id == "gsm"

    def test_mcc_latlon(self):
        sample = dict(radio=Radio.gsm, mnc=6, lac=1, cid=2, lat=GB_LAT, lon=GB_LON)
        assert CellObservation.create(mcc=GB_MCC, **sample) is not None
        assert CellObservation.create(mcc=262, **sample) is None

    def test_json(self):
        obs = CellObservationFactory.build(accuracy=None, source="fixed")
        result = CellObservation.from_json(json.loads(json.dumps(obs.to_json())))

        assert type(result) is CellObservation
        assert result.accuracy is None
        assert type(result.radio), Radio
        assert result.radio == obs.radio
        assert result.mcc == obs.mcc
        assert result.mnc == obs.mnc
        assert result.lac == obs.lac
        assert result.cid == obs.cid
        assert result.lat == obs.lat
        assert result.lon == obs.lon
        assert result.source is ReportSource.fixed
        assert type(result.source) is ReportSource

    def test_weight(self):
        obs_factory = CellObservationFactory.build

        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=None, signal=-95).weight, 2)
            == 1.0
        )
        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=0.0, signal=-95).weight, 2)
            == 1.0
        )
        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=10.0, signal=-95).weight, 2)
            == 1.0
        )
        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=160, signal=-95).weight, 2)
            == 0.25
        )
        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=200, signal=-95).weight, 2)
            == 0.22
        )
        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=1000, signal=-95).weight, 2)
            == 0.1
        )
        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=1000.1, signal=-95).weight, 2)
            == 0.0
        )

        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=10.0, signal=-51).weight, 2)
            == 10.17
        )
        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=160.0, signal=-51).weight, 2)
            == 2.54
        )
        assert (
            round(obs_factory(radio=Radio.gsm, accuracy=10.0, signal=-113).weight, 2)
            == 0.52
        )

        assert (
            round(obs_factory(radio=Radio.wcdma, accuracy=10.0, signal=-25).weight, 2)
            == 256.0
        )
        assert (
            round(obs_factory(radio=Radio.wcdma, accuracy=160.0, signal=-25).weight, 2)
            == 64.0
        )
        assert (
            round(obs_factory(radio=Radio.wcdma, accuracy=10.0, signal=-121).weight, 2)
            == 0.47
        )

        assert (
            round(obs_factory(radio=Radio.lte, accuracy=10.0, signal=-43).weight, 2)
            == 47.96
        )
        assert (
            round(obs_factory(radio=Radio.lte, accuracy=160.0, signal=-43).weight, 2)
            == 11.99
        )
        assert (
            round(obs_factory(radio=Radio.lte, accuracy=10.0, signal=-140).weight, 2)
            == 0.3
        )

        assert round(obs_factory(accuracy=0, age=1000).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, age=8000).weight, 2) == 0.5
        assert round(obs_factory(accuracy=0, age=20001).weight, 2) == 0.0

        assert round(obs_factory(accuracy=0, speed=None).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, speed=0.0).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, speed=1.0).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, speed=20.0).weight, 2) == 0.5
        assert round(obs_factory(accuracy=0, speed=50.1).weight, 2) == 0.0


class TestCellReport(BaseTest):
    def sample(self, **kwargs):
        report = {"radio": Radio.gsm, "mcc": GB_MCC, "mnc": 1, "lac": 2, "cid": 3}
        for (k, v) in kwargs.items():
            report[k] = v
        return CellReport.validate(report)

    def test_cellid(self):
        assert self.sample() is not None
        assert self.sample(radio=None) is None
        assert self.sample(mcc=None) is None
        assert self.sample(mnc=None) is None
        assert self.sample(lac=None) is None
        assert self.sample(cid=None) is None

    def test_radio(self):
        field = "radio"
        self.compare(field, "gsm", Radio.gsm)
        self.compare(field, "wcdma", Radio.wcdma)
        self.compare(field, "lte", Radio.lte)
        assert self.sample(radio="cdma") is None
        assert self.sample(radio="hspa") is None
        assert self.sample(radio="wimax") is None

    def test_mcc(self):
        self.compare("mcc", 262, 262)
        assert self.sample(mcc=constants.MIN_MCC - 1) is None
        assert self.sample(mcc=constants.MAX_MCC + 1) is None

    def test_mnc(self):
        self.compare("mnc", 5, 5)
        assert self.sample(mnc=constants.MIN_MNC - 1) is None
        assert self.sample(mnc=constants.MAX_MNC + 1) is None

    def test_lac(self):
        self.compare("lac", 5, 5)
        assert self.sample(lac=constants.MIN_LAC - 1) is None
        assert self.sample(lac=constants.MAX_LAC + 1) is None

    def test_lac_cid(self):
        assert (
            self.sample(radio=Radio.gsm, lac=None, cid=constants.MAX_CID_GSM, psc=None)
            is None
        )
        assert (
            self.sample(radio=Radio.gsm, lac=None, cid=constants.MAX_CID_GSM, psc=1)
            is None
        )

    def test_cid(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            assert self.sample(radio=radio, cid=constants.MIN_CID - 1) is None
            assert self.sample(radio=radio, cid=12345)["cid"] == 12345
            assert self.sample(radio=radio, cid=constants.MAX_CID + 1) is None

        # correct radio type for large GSM cid
        cid = constants.MAX_CID_GSM + 1
        assert self.sample(radio=Radio.gsm, cid=cid)["radio"] is Radio.wcdma
        # accept large WCDMA/LTE cid
        assert self.sample(radio=Radio.wcdma, cid=cid)["cid"] == cid
        assert self.sample(radio=Radio.lte, cid=cid)["cid"] == cid

    def test_psc(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            assert self.sample(radio=radio, psc=constants.MIN_PSC - 1)["psc"] is None
            assert self.sample(radio=radio, psc=15)["psc"] == 15
            assert self.sample(radio=radio, cid=constants.MAX_PSC + 1)["psc"] is None

        assert (
            self.sample(radio=Radio.lte, psc=constants.MAX_PSC_LTE + 1)["psc"] is None
        )

    def test_age(self):
        field = "age"
        self.compare(field, constants.MIN_AGE - 1, None)
        self.compare(field, -40000, -40000)
        self.compare(field, 60000, 60000)
        self.compare(field, constants.MAX_AGE + 1, None)

    def test_asu(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            assert (
                self.sample(radio=radio, asu=constants.MIN_CELL_ASU[radio] - 1)["asu"]
                is None
            )
            assert self.sample(radio=radio, asu=15)["asu"] == 15
            assert (
                self.sample(radio=radio, asu=constants.MAX_CELL_ASU[radio] + 1)["asu"]
                is None
            )

    def test_asu_signal(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            # if both are specified, leave them untouched
            assert self.sample(radio=radio, asu=15, signal=-75)["signal"] == -75

        for radio, signal in ((Radio.gsm, -83), (Radio.wcdma, -101), (Radio.lte, -125)):
            # calculate signal from asu
            assert self.sample(radio=radio, asu=15, signal=None)["signal"] == signal
            # switch asu/signal fields
            assert self.sample(radio=radio, asu=signal, signal=None)["signal"] == signal
            assert self.sample(radio=radio, asu=signal, signal=10)["signal"] == signal

    def test_signal(self):
        for radio in (Radio.gsm, Radio.wcdma, Radio.lte):
            assert (
                self.sample(radio=radio, signal=constants.MIN_CELL_SIGNAL[radio] - 1)[
                    "signal"
                ]
                is None
            )
            assert self.sample(radio=radio, signal=-75)["signal"] == -75
            assert (
                self.sample(radio=radio, signal=constants.MAX_CELL_SIGNAL[radio] + 1)[
                    "signal"
                ]
                is None
            )

    def test_ta(self):
        field = "ta"
        self.compare(field, constants.MIN_CELL_TA - 1, None)
        self.compare(field, 0, 0)
        self.compare(field, 31, 31)
        self.compare(field, constants.MAX_CELL_TA + 1, None)

        assert self.sample(radio=Radio.gsm, ta=1)["ta"] == 1
        assert self.sample(radio=Radio.wcdma, ta=1)["ta"] is None
        assert self.sample(radio=Radio.lte, ta=1)["ta"] == 1


class TestWifiObservation(BaseTest):
    def test_invalid(self):
        assert WifiObservation.create(mac="3680873e9b83", lat=0.0, lon=0.0) is None
        assert WifiObservation.create(mac="", lat=0.0, lon=0.0) is None

    def test_fields(self):
        mac = "3680873e9b83"
        obs = WifiObservation.create(
            mac=mac,
            lat=GB_LAT,
            lon=GB_LON,
            pressure=1010.2,
            source=ReportSource.query,
            timestamp=1405602028568,
            channel=5,
            signal=-45,
        )

        assert obs.lat == GB_LAT
        assert obs.lon == GB_LON
        assert obs.mac == mac
        assert obs.pressure == 1010.2
        assert obs.source == ReportSource.query
        assert obs.timestamp == 1405602028568
        assert obs.channel == 5
        assert obs.signal == -45
        assert obs.shard_id == "8"

    def test_json(self):
        obs = WifiObservationFactory.build(accuracy=None, source=ReportSource.query)
        result = WifiObservation.from_json(json.loads(json.dumps(obs.to_json())))

        assert type(result) is WifiObservation
        assert result.accuracy is None
        assert result.mac == obs.mac
        assert result.lat == obs.lat
        assert result.lon == obs.lon
        assert result.source == ReportSource.query
        assert type(result.source) is ReportSource

    def test_weight(self):
        obs_factory = WifiObservationFactory.build
        assert round(obs_factory(accuracy=None, signal=-80).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0.0, signal=-80).weight, 2) == 1.0
        assert round(obs_factory(accuracy=10.0, signal=-80).weight, 2) == 1.0
        assert round(obs_factory(accuracy=40.0, signal=-80).weight, 2) == 0.5
        assert round(obs_factory(accuracy=100, signal=-80).weight, 2) == 0.32
        assert round(obs_factory(accuracy=200, signal=-80).weight, 2) == 0.22
        assert round(obs_factory(accuracy=200.1, signal=-80).weight, 2) == 0.0

        assert round(obs_factory(accuracy=10, signal=-100).weight, 2) == 0.48
        assert round(obs_factory(accuracy=10, signal=-30).weight, 2) == 16.0
        assert round(obs_factory(accuracy=10, signal=-10).weight, 2) == 123.46

        assert round(obs_factory(accuracy=40, signal=-30).weight, 2) == 8.0
        assert round(obs_factory(accuracy=100, signal=-30).weight, 2) == 5.06
        assert round(obs_factory(accuracy=100, signal=-10).weight, 2) == 39.04

        assert round(obs_factory(accuracy=0, age=0).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, age=1000).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, age=-1000).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, age=5000).weight, 2) == 0.63
        assert round(obs_factory(accuracy=0, age=8000).weight, 2) == 0.5
        assert round(obs_factory(accuracy=0, age=20001).weight, 2) == 0.0

        assert round(obs_factory(accuracy=0, speed=None).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, speed=0.0).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, speed=1.0).weight, 2) == 1.0
        assert round(obs_factory(accuracy=0, speed=20.0).weight, 2) == 0.5
        assert round(obs_factory(accuracy=0, speed=50.1).weight, 2) == 0.0


class TestWifiReport(BaseTest):
    def sample(self, **kwargs):
        report = {"mac": "3680873e9b83"}
        for (k, v) in kwargs.items():
            report[k] = v
        return WifiReport.validate(report)

    def test_mac(self):
        assert self.sample(mac="3680873e9b83") is not None
        assert self.sample(mac="3680873E9B83") is not None
        assert self.sample(mac="36:80:87:3e:9b:83") is not None
        assert self.sample(mac="36-80-87-3e-9b-83") is not None
        assert self.sample(mac="36.80.87.3e.9b.83") is not None
        # We considered but do not ban locally administered WiFi
        # mac addresses based on the U/L bit
        # https://en.wikipedia.org/wiki/MAC_address
        assert self.sample(mac="0a0000000000") is not None

        assert self.sample(mac="") is None
        assert self.sample(mac="1234567890123") is None
        assert self.sample(mac="aaaaaaZZZZZZ") is None
        assert self.sample(mac="000000000000") is None
        assert self.sample(mac="ffffffffffff") is None
        assert self.sample(mac=constants.WIFI_TEST_MAC) is None

    def test_age(self):
        field = "age"
        self.compare(field, constants.MIN_AGE - 1, None)
        self.compare(field, -40000, -40000)
        self.compare(field, 60000, 60000)
        self.compare(field, constants.MAX_AGE + 1, None)

    def test_channel(self):
        field = "channel"
        self.compare(field, constants.MIN_WIFI_CHANNEL - 1, None)
        self.compare(field, 1, 1)
        self.compare(field, 36, 36)
        self.compare(field, constants.MAX_WIFI_CHANNEL + 1, None)

    def test_channel_frequency(self):
        sample = self.sample(channel=0, frequency=10)
        assert sample["channel"] is None
        assert sample["frequency"] is None

        sample = self.sample(channel=0, frequency=2412)
        assert sample["channel"] == 1
        assert sample["frequency"] == 2412

        sample = self.sample(channel=4, frequency=10)
        assert sample["channel"] == 4
        assert sample["frequency"] == 2427

        sample = self.sample(channel=1, frequency=2427)
        assert sample["channel"] == 1
        assert sample["frequency"] == 2427

    def test_frequency(self):
        field = "frequency"
        self.compare(field, constants.MIN_WIFI_FREQUENCY - 1, None)
        self.compare(field, 2412, 2412)
        self.compare(field, 2484, 2484)
        self.compare(field, 4915, 4915)
        self.compare(field, 5170, 5170)
        self.compare(field, 5925, 5925)
        self.compare(field, constants.MAX_WIFI_FREQUENCY + 1, None)

    def test_signal(self):
        field = "signal"
        self.compare(field, constants.MIN_WIFI_SIGNAL - 1, None)
        self.compare(field, -90, -90)
        self.compare(field, -10, -10)
        self.compare(field, constants.MAX_WIFI_SIGNAL + 1, None)

    def test_snr(self):
        field = "snr"
        self.compare(field, constants.MIN_WIFI_SNR - 1, None)
        self.compare(field, 1, 1)
        self.compare(field, 40, 40)
        self.compare(field, constants.MAX_WIFI_SNR + 1, None)
