import colander
import pytest
import requests_mock
from sqlalchemy import text

from ichnaea.api.locate.constants import (
    BLUE_MIN_ACCURACY,
    CELL_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.api.locate.schema_v1 import LOCATE_V1_SCHEMA
from ichnaea.api.locate.tests.base import BaseLocateTest, CommonLocateTest
from ichnaea.conftest import GEOIP_DATA
from ichnaea.models import ApiKey, CellArea, Radio
from ichnaea.tests.factories import (
    ApiKeyFactory,
    BlueShardFactory,
    CellAreaFactory,
    CellShardFactory,
    WifiShardFactory,
)
from ichnaea import util


class TestSchema(object):
    def test_empty(self):
        data = LOCATE_V1_SCHEMA.deserialize({})
        assert data == {
            "bluetoothBeacons": (),
            "carrier": None,
            "cellTowers": (),
            "considerIp": True,
            "fallbacks": {"ipf": True, "lacf": True},
            "homeMobileCountryCode": None,
            "homeMobileNetworkCode": None,
            "wifiAccessPoints": (),
        }

    def test_consider_ip(self):
        data = LOCATE_V1_SCHEMA.deserialize({"considerIp": False})
        assert data["fallbacks"]["ipf"] is False
        data = LOCATE_V1_SCHEMA.deserialize({"considerIp": "false"})
        assert data["fallbacks"]["ipf"] is False
        data = LOCATE_V1_SCHEMA.deserialize({"considerIp": "true"})
        assert data["fallbacks"]["ipf"] is True
        data = LOCATE_V1_SCHEMA.deserialize({"considerIp": False, "fallbacks": {}})
        assert data["fallbacks"]["ipf"] is True

    def test_invalid_radio_field(self):
        with pytest.raises(colander.Invalid):
            LOCATE_V1_SCHEMA.deserialize({"cellTowers": [{"radioType": "umts"}]})

    def test_multiple_radio_fields(self):
        data = LOCATE_V1_SCHEMA.deserialize(
            {"cellTowers": [{"radio": "gsm", "radioType": "wcdma"}]}
        )
        assert data["cellTowers"][0]["radioType"] == "wcdma"
        assert "radio" not in data["cellTowers"][0]


class LocateV1Base(BaseLocateTest):

    url = "/v1/geolocate"
    metric_path = "path:v1.geolocate"
    metric_type = "locate"

    @property
    def ip_response(self):
        london = GEOIP_DATA["London"]
        return {
            "location": {"lat": london["latitude"], "lng": london["longitude"]},
            "accuracy": london["radius"],
        }

    def check_model_response(self, response, model, region=None, fallback=None, **kw):
        expected_names = set(["location", "accuracy"])

        expected = super(LocateV1Base, self).check_model_response(
            response,
            model,
            region=region,
            fallback=fallback,
            expected_names=expected_names,
            **kw,
        )

        data = response.json
        location = data["location"]
        assert round(location["lat"], 7) == round(expected["lat"], 7)
        assert round(location["lng"], 7) == round(expected["lon"], 7)
        assert data["accuracy"] == expected["accuracy"]
        if fallback is not None:
            assert data["fallback"] == fallback


class TestView(LocateV1Base, CommonLocateTest):
    def test_api_key_limit(self, app, data_queues, redis, session, logs):
        """When daily API limit is reached, a 403 is returned."""
        api_key = ApiKeyFactory(maxreq=5)
        session.flush()

        # exhaust today's limit
        dstamp = util.utcnow().strftime("%Y%m%d")
        path = self.metric_path.split(":")[-1]
        key = "apilimit:%s:%s:%s" % (api_key.valid_key, path, dstamp)
        redis.incr(key, 10)

        res = self._call(app, api_key=api_key.valid_key, ip=self.test_ip, status=403)
        self.check_response(data_queues, res, "limit_exceeded")

        expected_entry = {
            "api_key": api_key.valid_key,
            "api_path": self.metric_path.split(":")[1],
            "api_type": self.metric_type,
            "duration_s": logs.entry["duration_s"],
            "event": f"POST {self.url} - 403",
            "http_method": "POST",
            "http_path": self.url,
            "http_status": 403,
            "log_level": "info",
        }
        assert logs.entry == expected_entry

    def test_api_key_blocked(self, app, data_queues, session, logs):
        """A 400 is returned when a key is blocked from locate APIs."""
        api_key = ApiKeyFactory(allow_locate=False, allow_region=False)
        session.flush()

        res = self._call(app, api_key=api_key.valid_key, ip=self.test_ip, status=400)
        self.check_response(data_queues, res, "invalid_key")

        log = logs.entry
        assert log["api_key"] == "invalid"
        assert log["api_key"] != api_key.valid_key

    def test_blue_not_found(self, app, data_queues, metricsmock, logs):
        """A failed Bluetooth-based lookup emits several metrics."""
        blues = BlueShardFactory.build_batch(2)

        query = self.model_query(blues=blues)

        res = self._call(app, body=query, status=404)
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:404"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".query",
            tags=["key:test", "geoip:false", "blue:many", "cell:none", "wifi:none"],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".result",
            tags=["key:test", "accuracy:high", "fallback_allowed:false", "status:miss"],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".source",
            tags=["key:test", "source:internal", "accuracy:high", "status:miss"],
        )
        assert logs.entry["blue"] == logs.entry["blue_valid"] == 2

    def test_cell_not_found(self, app, data_queues, metricsmock, logs):
        """A failed cell-based lookup emits several metrics."""
        cell = CellShardFactory.build()

        query = self.model_query(cells=[cell])
        res = self._call(app, body=query, status=404)
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:404"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".query",
            tags=["key:test", "geoip:false", "blue:none", "cell:one", "wifi:none"],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".result",
            tags=[
                "key:test",
                "fallback_allowed:false",
                "accuracy:medium",
                "status:miss",
            ],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".source",
            tags=["key:test", "source:internal", "accuracy:medium", "status:miss"],
        )
        assert logs.entry["cell"] == logs.entry["cell_valid"] == 1

    def test_cell_invalid_lac(self, app, data_queues, logs):
        """A valid CID with and invalid LAC is not an error."""
        cell = CellShardFactory.build(radio=Radio.wcdma, lac=0, cid=1)
        query = self.model_query(cells=[cell])
        res = self._call(app, body=query, status=404)
        self.check_response(data_queues, res, "not_found")

        assert logs.entry["cell"] == 1
        assert logs.entry["cell_valid"] == 0

    def test_cell_lte_radio(self, app, session, metricsmock, logs):
        """A known LTE station can be used for lookups."""
        cell = CellShardFactory(radio=Radio.lte)
        session.flush()

        query = self.model_query(cells=[cell])
        res = self._call(app, body=query)
        self.check_model_response(res, cell)
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:200"]
        )
        assert logs.entry["cell"] == logs.entry["cell_valid"] == 1

    @pytest.mark.parametrize("fallback", ("explicit", "default", "ipf"))
    def test_cellarea(self, app, session, metricsmock, fallback, logs):
        """
        A unknown cell in a known cell area can be a hit, with fallback enabled.

        The cell location area fallback (lacf) is on by default, or can be
        explicitly enabled.
        """
        cell = CellAreaFactory()
        session.flush()

        query = self.model_query(cells=[cell])
        if fallback == "explicit":
            query["fallbacks"] = {"lacf": True}
        elif fallback == "ipf":
            # Enabling IP fallback leaves lac fallback at default
            query["fallbacks"] = {"ipf": True}
        res = self._call(app, body=query)
        self.check_model_response(res, cell, fallback="lacf")
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:200"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".query",
            tags=["key:test", "geoip:false", "blue:none", "cell:none", "wifi:none"],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".result",
            tags=[
                "key:test",
                "fallback_allowed:false",
                "accuracy:low",
                "status:hit",
                "source:internal",
            ],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".source",
            tags=["key:test", "source:internal", "accuracy:low", "status:hit"],
        )
        assert logs.entry["cell"] == 1
        assert logs.entry["cell_valid"] == 0

    def test_cellarea_without_lacf(self, app, data_queues, session, metricsmock, logs):
        """The cell location area fallback can be disabled."""
        cell = CellAreaFactory()
        session.flush()

        query = self.model_query(cells=[cell])
        query["fallbacks"] = {"lacf": False}

        res = self._call(app, body=query, status=404)
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:404"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )

        assert logs.entry["cell"] == 1
        assert logs.entry["cell_valid"] == 0

    def test_wifi_not_found(self, app, data_queues, metricsmock, logs):
        """A failed WiFi-based lookup emits several metrics."""
        wifis = WifiShardFactory.build_batch(2)

        query = self.model_query(wifis=wifis)

        res = self._call(app, body=query, status=404)
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:404"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".query",
            tags=["key:test", "geoip:false", "blue:none", "cell:none", "wifi:many"],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".result",
            tags=["key:test", "accuracy:high", "fallback_allowed:false", "status:miss"],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".source",
            tags=["key:test", "source:internal", "accuracy:high", "status:miss"],
        )
        assert logs.entry["wifi"] == logs.entry["wifi_valid"] == 2

    def test_ip_fallback_disabled(self, app, data_queues, metricsmock, logs):
        """The IP-based location fallback can be disabled."""
        res = self._call(
            app, body={"fallbacks": {"ipf": 0}}, ip=self.test_ip, status=404
        )
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:404"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        assert logs.entry["has_geoip"]
        assert "source_geoip_status" not in logs.entry

    @pytest.mark.parametrize("with_ip", [True, False])
    def test_fallback(self, app, session, metricsmock, with_ip, logs):
        """
        An external location provider can be used to improve results.

        A cell + wifi based query which gets a cell based internal result and
        continues on to the fallback to get a better wifi based result.
        The fallback may or may not include IP-based lookup data.
        """
        cells = CellShardFactory.create_batch(2, radio=Radio.wcdma)
        wifis = WifiShardFactory.build_batch(3)
        ApiKeyFactory(valid_key="fall", allow_fallback=True)
        session.flush()

        with requests_mock.Mocker() as mock:
            response_result = {"location": {"lat": 1.0, "lng": 1.0}, "accuracy": 100}
            mock.register_uri("POST", requests_mock.ANY, json=response_result)

            query = self.model_query(cells=cells, wifis=wifis)
            if with_ip:
                ip = self.test_ip
            else:
                ip = None
            res = self._call(app, api_key="fall", body=query, ip=ip)

            send_json = mock.request_history[0].json()
            assert len(send_json["cellTowers"]) == 2
            assert len(send_json["wifiAccessPoints"]) == 3
            assert send_json["cellTowers"][0]["radioType"] == "wcdma"

        self.check_model_response(res, None, lat=1.0, lon=1.0, accuracy=100)
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:200"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:fall"]
        )
        if with_ip:
            metricsmock.assert_incr_once(
                self.metric_type + ".query",
                tags=["key:fall", "blue:none", "cell:many", "wifi:many"],
            )
        else:
            metricsmock.assert_incr_once(
                self.metric_type + ".query",
                tags=["key:fall", "geoip:false", "blue:none", "cell:many", "wifi:many"],
            )
        metricsmock.assert_incr_once(
            self.metric_type + ".result",
            tags=[
                "key:fall",
                "fallback_allowed:true",
                "accuracy:high",
                "status:hit",
                "source:fallback",
            ],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".source",
            tags=["key:fall", "source:internal", "accuracy:high", "status:miss"],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".source",
            tags=["key:fall", "source:fallback", "accuracy:high", "status:hit"],
        )

        log = logs.entry
        assert log["cell"] == log["cell_valid"] == 2
        assert log["wifi"] == log["wifi_valid"] == 3
        assert log["fallback_allowed"]
        assert log["source_fallback_accuracy"] == "high"
        assert log["source_fallback_accuracy_min"] == "high"
        assert log["source_fallback_status"] == "hit"

    def test_store_sample_disabled(self, app, data_queues, session):
        """No requests are processed when store_sample_locate=0."""
        api_key = ApiKeyFactory(store_sample_locate=0)
        cell = CellShardFactory()
        session.flush()

        query = self.model_query(cells=[cell])
        res = self._call(app, body=query, api_key=api_key.valid_key, status=200)
        self.check_model_response(res, cell)
        self.check_queue(data_queues, 0)

    def test_blue(self, app, data_queues, session, metricsmock):
        """Bluetooth can be used for location."""
        blue = BlueShardFactory()
        offset = 0.00001
        blues = [
            blue,
            BlueShardFactory(lat=blue.lat + offset),
            BlueShardFactory(lat=blue.lat + offset * 2),
            BlueShardFactory(lat=None, lon=None),
        ]
        session.flush()

        query = self.model_query(blues=blues)
        blue_query = query["bluetoothBeacons"]
        blue_query[0]["signalStrength"] = -50
        blue_query[1]["signalStrength"] = -150
        blue_query[1]["name"] = "my-beacon"

        res = self._call(app, body=query)
        self.check_model_response(res, blue, lat=blue.lat + 0.0000035)
        self.check_queue(data_queues, 1)
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".result",
            tags=[
                "key:test",
                "fallback_allowed:false",
                "accuracy:high",
                "status:hit",
                "source:internal",
            ],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".source",
            tags=["key:test", "source:internal", "accuracy:high", "status:hit"],
        )
        items = data_queues["update_incoming"].dequeue()
        assert items == [
            {
                "api_key": "test",
                "source": "query",
                "report": {
                    "bluetoothBeacons": [
                        {
                            "macAddress": blue_query[0]["macAddress"],
                            "signalStrength": -50,
                        },
                        {
                            "macAddress": blue_query[1]["macAddress"],
                            "name": "my-beacon",
                        },
                        {"macAddress": blue_query[2]["macAddress"]},
                        {"macAddress": blue_query[3]["macAddress"]},
                    ],
                    "fallbacks": {"ipf": True, "lacf": True},
                    "position": {
                        "accuracy": BLUE_MIN_ACCURACY,
                        "latitude": blue.lat + 0.0000035,
                        "longitude": blue.lon,
                        "source": "query",
                    },
                },
            }
        ]

    @pytest.mark.parametrize("mac", ["a82067491500", "a82067491501"])
    def test_blue_seen(self, app, data_queues, session, mac):
        """If a query contains no new data, it is not queued for further processing.

        Due to an issue with truncating bytestrings in a numpy array (numpy
        issue 8089), addresses that end in '00' were once detected as new
        stations.
        """

        self.check_queue(data_queues, 0)
        blue = BlueShardFactory(mac=mac)
        offset = 0.00002
        blues = [blue, BlueShardFactory(lat=blue.lat + offset)]
        session.flush()
        self.check_queue(data_queues, 0)
        query = self.model_query(blues=blues)
        res = self._call(app, body=query)
        self.check_model_response(res, blue, lat=blue.lat + offset / 2)
        if data_queues["update_incoming"].size():
            items = data_queues["update_incoming"].dequeue()
            pytest.fail(
                (
                    "Query added a report to the update_incoming queue."
                    "\nQuery:\n{}\nReport:\n{}"
                ).format(query, items)
            )

    def test_cell(self, app, data_queues, session, metricsmock):
        """Cell stations can be used for location."""
        cell = CellShardFactory(radio=Radio.lte)
        session.flush()

        query = self.model_query(cells=[cell])
        query["radioType"] = cell.radio.name
        del query["cellTowers"][0]["radioType"]
        query["cellTowers"][0]["signalStrength"] = -70
        query["cellTowers"][0]["timingAdvance"] = 1

        res = self._call(app, body=query)
        self.check_model_response(res, cell)
        self.check_queue(data_queues, 1)
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:200"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".result",
            tags=[
                "key:test",
                "fallback_allowed:false",
                "accuracy:medium",
                "status:hit",
                "source:internal",
            ],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".source",
            tags=["key:test", "source:internal", "accuracy:medium", "status:hit"],
        )
        items = data_queues["update_incoming"].dequeue()
        assert items == [
            {
                "api_key": "test",
                "source": "query",
                "report": {
                    "cellTowers": [
                        {
                            "radioType": cell.radio.name,
                            "mobileCountryCode": cell.mcc,
                            "mobileNetworkCode": cell.mnc,
                            "locationAreaCode": cell.lac,
                            "cellId": cell.cid,
                            "primaryScramblingCode": cell.psc,
                            "signalStrength": -70,
                            "timingAdvance": 1,
                        }
                    ],
                    "fallbacks": {"ipf": True, "lacf": True},
                    "position": {
                        "accuracy": CELL_MIN_ACCURACY,
                        "latitude": cell.lat,
                        "longitude": cell.lon,
                        "source": "query",
                    },
                },
            }
        ]

    def test_partial_cell(self, app, data_queues, session):
        """A partial cell is ignored for location."""
        cell = CellShardFactory()
        session.flush()

        # simulate one neighboring incomplete cell
        query = self.model_query(cells=[cell])
        query["cellTowers"][0]["psc"] = cell.psc

        cell_two = query["cellTowers"][0].copy()
        del cell_two["locationAreaCode"]
        del cell_two["cellId"]
        cell_two["psc"] = cell.psc + 1
        query["cellTowers"].append(cell_two)

        res = self._call(app, body=query)
        self.check_model_response(res, cell)
        self.check_queue(data_queues, 1)

    def test_wifi(self, app, data_queues, session, metricsmock):
        """WiFi can be used for location."""
        wifi = WifiShardFactory()
        offset = 0.00001
        wifis = [
            wifi,
            WifiShardFactory(lat=wifi.lat + offset),
            WifiShardFactory(lat=wifi.lat + offset * 2),
            WifiShardFactory(lat=None, lon=None),
        ]
        session.flush()

        query = self.model_query(wifis=wifis)
        wifi_query = query["wifiAccessPoints"]
        wifi_query[0]["channel"] = 1
        wifi_query[0]["signalStrength"] = -50
        wifi_query[1]["frequency"] = 2437
        wifi_query[2]["signalStrength"] = -130
        wifi_query[2]["signalToNoiseRatio"] = 13
        wifi_query[3]["ssid"] = "my-wifi"

        res = self._call(app, body=query)
        self.check_model_response(res, wifi, lat=wifi.lat + 0.000005)
        self.check_queue(data_queues, 1)
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:200"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".result",
            tags=[
                "key:test",
                "fallback_allowed:false",
                "accuracy:high",
                "status:hit",
                "source:internal",
            ],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".source",
            tags=["key:test", "source:internal", "accuracy:high", "status:hit"],
        )
        items = data_queues["update_incoming"].dequeue()
        assert items == [
            {
                "api_key": "test",
                "source": "query",
                "report": {
                    "wifiAccessPoints": [
                        {
                            "macAddress": wifi_query[0]["macAddress"],
                            "channel": 1,
                            "frequency": 2412,
                            "signalStrength": -50,
                        },
                        {
                            "macAddress": wifi_query[1]["macAddress"],
                            "channel": 6,
                            "frequency": 2437,
                        },
                        {
                            "macAddress": wifi_query[2]["macAddress"],
                            "signalToNoiseRatio": 13,
                        },
                        {"macAddress": wifi_query[3]["macAddress"], "ssid": "my-wifi"},
                    ],
                    "fallbacks": {"ipf": True, "lacf": True},
                    "position": {
                        "accuracy": WIFI_MIN_ACCURACY,
                        "latitude": wifi.lat + 0.000005,
                        "longitude": wifi.lon,
                        "source": "query",
                    },
                },
            }
        ]

    def test_cell_mcc_mnc_strings(self, app, session):
        """
        Mobile country and network codes can be formatted as strings.

        mcc and mnc are officially defined as strings, where '01' is
        different from '1'. In practice many systems ours included treat
        them as integers, so both of these are encoded as 1 instead.
        Some clients sends us these values as strings, some as integers,
        so we want to make sure we support both.
        """
        cell = CellShardFactory(mnc=1)
        session.flush()

        query = self.model_query(cells=[cell])
        query["cellTowers"][0]["mobileCountryCode"] = str(cell.mcc)
        query["cellTowers"][0]["mobileNetworkCode"] = "01"

        res = self._call(app, body=query)
        self.check_model_response(res, cell)

    def test_cell_radiotype_in_celltowers(self, app, session):
        """The geolocate API has a extension radioType for cellTowers."""
        cell = CellShardFactory()
        session.flush()

        query = self.model_query(cells=[cell])
        query["cellTowers"][0]["radioType"] = cell.radio.name

        res = self._call(app, body=query)
        self.check_model_response(res, cell)

    def test_inconsistent_cell_radio(self, app, session):
        """A radioType in a cellTower entry overrides the global radioType"""
        cell = CellShardFactory(radio=Radio.wcdma, radius=15000, samples=10)
        cell2 = CellShardFactory(
            radio=Radio.gsm,
            radius=35000,
            samples=5,
            lat=cell.lat + 0.0002,
            lon=cell.lon,
        )
        session.flush()

        query = self.model_query(cells=[cell, cell2])
        query["radioType"] = Radio.lte.name
        query["cellTowers"][0]["radioType"] = "wcdma"
        query["cellTowers"][1]["radioType"] = cell2.radio.name

        res = self._call(app, body=query)
        self.check_model_response(res, cell)

    def test_cdma_cell(self, app, session):
        """A CDMA radio is not an error, but the information is ignored."""
        cell = CellShardFactory(radio=Radio.gsm, radius=15000)
        cell2 = CellShardFactory(
            radio=Radio.gsm, radius=35000, lat=cell.lat + 0.0002, lon=cell.lon
        )
        cell2.radio = Radio.cdma
        session.flush()

        query = self.model_query(cells=[cell, cell2])
        res = self._call(app, body=query)
        self.check_model_response(res, cell)


class TestError(LocateV1Base, BaseLocateTest):
    def test_apikey_error(self, app, data_queues, raven, session, restore_db, logs):
        cells = CellShardFactory.build_batch(2)
        wifis = WifiShardFactory.build_batch(2)

        session.execute(text("drop table %s;" % ApiKey.__tablename__))

        query = self.model_query(cells=cells, wifis=wifis)
        res = self._call(app, body=query, ip=self.test_ip)
        self.check_response(data_queues, res, "ok", fallback="ipf")
        raven.check([("ProgrammingError", 1)])
        self.check_queue(data_queues, 0)
        expected_entry = {
            "blue": 0,
            "blue_valid": 0,
            "cell": 2,
            "cell_valid": 2,
            "duration_s": logs.entry["duration_s"],
            "event": "POST /v1/geolocate - 200",
            "has_geoip": True,
            "has_ip": True,
            "http_method": "POST",
            "http_path": "/v1/geolocate",
            "http_status": 200,
            "log_level": "info",
            "region": "GB",
            "wifi": 2,
            "wifi_valid": 2,
        }
        assert logs.entry == expected_entry

    def test_database_error(
        self, app, data_queues, raven, session, metricsmock, restore_db, logs
    ):
        cells = [
            CellShardFactory.build(radio=Radio.gsm),
            CellShardFactory.build(radio=Radio.wcdma),
            CellShardFactory.build(radio=Radio.lte),
        ]
        wifis = WifiShardFactory.build_batch(2)

        for model in (CellArea,):
            session.execute(text("drop table %s;" % model.__tablename__))
        for name in set([cell.__tablename__ for cell in cells]):
            session.execute(text("drop table %s;" % name))
        for name in set([wifi.__tablename__ for wifi in wifis]):
            session.execute(text("drop table %s;" % name))

        query = self.model_query(cells=cells, wifis=wifis)
        res = self._call(app, body=query, ip=self.test_ip)
        self.check_response(data_queues, res, "ok", fallback="ipf")
        self.check_queue(data_queues, 0)
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:200"]
        )
        if self.apikey_metrics:
            metricsmock.assert_incr_once(
                self.metric_type + ".result",
                tags=[
                    "key:test",
                    "fallback_allowed:false",
                    "accuracy:high",
                    "status:miss",
                ],
            )

        raven.check([("ProgrammingError", 3)])
        expected_entry = {
            "accuracy": "medium",
            "accuracy_min": "high",
            "api_key": "test",
            "api_path": "v1.geolocate",
            "api_type": "locate",
            "blue": 0,
            "blue_valid": 0,
            "cell": 3,
            "cell_valid": 3,
            "duration_s": logs.entry["duration_s"],
            "event": "POST /v1/geolocate - 200",
            "fallback_allowed": False,
            "has_geoip": True,
            "has_ip": True,
            "http_method": "POST",
            "http_path": "/v1/geolocate",
            "http_status": 200,
            "log_level": "info",
            "region": "GB",
            "result_status": "miss",
            "source_geoip_accuracy": "medium",
            "source_geoip_accuracy_min": "high",
            "source_geoip_status": "miss",
            "source_internal_accuracy": None,
            "source_internal_accuracy_min": "high",
            "source_internal_status": "miss",
            "wifi": 2,
            "wifi_valid": 2,
        }

        assert logs.entry == expected_entry
