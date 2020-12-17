from datetime import datetime
from zoneinfo import ZoneInfo

import colander
import pytest

from ichnaea.api.exceptions import ParseError
from ichnaea.api.submit.schema_v0 import SUBMIT_V0_SCHEMA
from ichnaea.api.submit.tests.base import BaseSubmitTest
from ichnaea.models import Radio
from ichnaea.tests.factories import BlueShardFactory, CellShardFactory, WifiShardFactory
from ichnaea import util


class TestSubmitSchema(object):
    def test_empty(self):
        with pytest.raises(colander.Invalid):
            SUBMIT_V0_SCHEMA.deserialize({})

    def test_empty_blue_entry(self):
        blue = BlueShardFactory.build()
        data = SUBMIT_V0_SCHEMA.deserialize(
            {"items": [{"lat": blue.lat, "lon": blue.lon, "blue": [{}]}]}
        )
        assert data == {"items": []}

    def test_cell_radio(self):
        cell = CellShardFactory.build()
        data = SUBMIT_V0_SCHEMA.deserialize(
            {
                "items": [
                    {
                        "lat": cell.lat,
                        "lon": cell.lon,
                        "cell": [
                            {
                                "radio": "UMTS",
                                "mcc": cell.mcc,
                                "mnc": cell.mnc,
                                "lac": cell.lac,
                                "cid": cell.cid,
                            }
                        ],
                    }
                ]
            }
        )
        assert data["items"][0]["cellTowers"][0]["radioType"] == "wcdma"

        cell = CellShardFactory.build()
        data = SUBMIT_V0_SCHEMA.deserialize(
            {
                "items": [
                    {
                        "lat": cell.lat,
                        "lon": cell.lon,
                        "cell": [
                            {
                                "radio": "foo",
                                "mcc": cell.mcc,
                                "mnc": cell.mnc,
                                "lac": cell.lac,
                                "cid": cell.cid,
                            }
                        ],
                    }
                ]
            }
        )
        assert "radioType" not in data["items"][0]["cellTowers"][0]

    def test_empty_wifi_entry(self):
        wifi = WifiShardFactory.build()
        data = SUBMIT_V0_SCHEMA.deserialize(
            {"items": [{"lat": wifi.lat, "lon": wifi.lon, "wifi": [{}]}]}
        )
        assert data == {"items": []}

    def test_minimal(self):
        wifi = WifiShardFactory.build()
        data = SUBMIT_V0_SCHEMA.deserialize(
            {"items": [{"lat": wifi.lat, "lon": wifi.lon, "wifi": [{"key": "ab"}]}]}
        )
        assert "items" in data
        assert len(data["items"]) == 1

    def test_timestamp(self):
        wifi = WifiShardFactory.build()

        data = SUBMIT_V0_SCHEMA.deserialize(
            {"items": [{"time": "2016-04-07T03:33:20", "wifi": [{"key": wifi.mac}]}]}
        )
        assert data["items"][0]["timestamp"] == 146 * 10 ** 10

        data = SUBMIT_V0_SCHEMA.deserialize(
            {"items": [{"time": "1710-02-28", "wifi": [{"key": wifi.mac}]}]}
        )
        # 1710 was discarded and replaced by 'now'
        assert data["items"][0]["timestamp"] > 10 ** 12


class TestView(BaseSubmitTest):

    url = "/v1/submit"
    metric_path = "path:v1.submit"
    status = 204
    radio_id = "radio"
    cells_id = "cell"

    def _one_cell_query(self, radio=True):
        cell = CellShardFactory.build()
        query = {
            "lat": cell.lat,
            "lon": cell.lon,
            "cell": [
                {"mcc": cell.mcc, "mnc": cell.mnc, "lac": cell.lac, "cid": cell.cid}
            ],
        }
        if radio:
            query["cell"][0]["radio"] = cell.radio.name
        return (cell, query)

    def test_blue(self, app, celery):
        blue = BlueShardFactory.build()
        res = self._post(
            app,
            [
                {
                    "lat": blue.lat,
                    "lon": blue.lon,
                    "source": "",
                    "blue": [
                        {"key": blue.mac, "age": 3000, "name": "beacon", "signal": -101}
                    ],
                }
            ],
        )
        assert res.body == b""

        assert self.queue(celery).size() == 1
        item = self.queue(celery).dequeue()[0]
        assert item["api_key"] is None
        report = item["report"]
        position = report["position"]
        assert position["latitude"] == blue.lat
        assert position["longitude"] == blue.lon
        assert "source" not in position
        blues = item["report"]["bluetoothBeacons"]
        assert len(blues) == 1
        assert blues[0]["macAddress"] == blue.mac
        assert blues[0]["age"] == 3000
        assert blues[0]["name"] == "beacon"
        assert blues[0]["signalStrength"] == -101

    def test_cell(self, app, celery):
        now = util.utcnow()
        today = now.replace(hour=0, minute=0, second=0)
        cell = CellShardFactory.build(radio=Radio.wcdma)
        res = self._post(
            app,
            [
                {
                    "lat": cell.lat,
                    "lon": cell.lon,
                    "time": today.strftime("%Y-%m-%d"),
                    "accuracy": 10.6,
                    "altitude": 123.1,
                    "altitude_accuracy": 7.0,
                    "heading": 45.2,
                    "pressure": 1020.23,
                    "speed": 3.6,
                    "source": "gnss",
                    "radio": cell.radio.name,
                    "cell": [
                        {
                            "radio": "umts",
                            "mcc": cell.mcc,
                            "mnc": cell.mnc,
                            "lac": cell.lac,
                            "cid": cell.cid,
                            "age": 1000,
                            "asu": 3,
                            "psc": 7,
                            "serving": 1,
                            "signal": -85,
                            "ta": 2,
                        }
                    ],
                }
            ],
            api_key="test",
        )
        assert res.body == b""

        assert self.queue(celery).size() == 1
        item = self.queue(celery).dequeue()[0]
        assert item["api_key"] == "test"
        report = item["report"]
        timestamp = datetime.utcfromtimestamp(report["timestamp"] / 1000.0)
        timestamp = timestamp.replace(microsecond=0, tzinfo=ZoneInfo("UTC"))
        assert timestamp == today
        position = report["position"]
        assert position["latitude"] == cell.lat
        assert position["longitude"] == cell.lon
        assert position["accuracy"] == 10.6
        assert position["altitude"] == 123.1
        assert position["altitudeAccuracy"] == 7.0
        assert position["heading"] == 45.2
        assert position["pressure"] == 1020.23
        assert position["speed"] == 3.6
        assert position["source"] == "gnss"
        cells = report["cellTowers"]
        assert cells[0]["radioType"] == "wcdma"
        assert cells[0]["mobileCountryCode"] == cell.mcc
        assert cells[0]["mobileNetworkCode"] == cell.mnc
        assert cells[0]["locationAreaCode"] == cell.lac
        assert cells[0]["cellId"] == cell.cid
        assert cells[0]["age"] == 1000
        assert cells[0]["asu"] == 3
        assert cells[0]["primaryScramblingCode"] == 7
        assert cells[0]["serving"] == 1
        assert cells[0]["signalStrength"] == -85
        assert cells[0]["timingAdvance"] == 2

    def test_wifi(self, app, celery):
        wifi = WifiShardFactory.build()
        self._post(
            app,
            [
                {
                    "lat": wifi.lat,
                    "lon": wifi.lon,
                    "accuracy": 17.1,
                    "source": "2",
                    "wifi": [
                        {
                            "key": wifi.mac.upper(),
                            "age": 2500,
                            "channel": 1,
                            "frequency": 2437,
                            "signal": -70,
                            "signalToNoiseRatio": 5,
                            "ssid": "my-wifi",
                        }
                    ],
                }
            ],
        )

        assert self.queue(celery).size() == 1
        item = self.queue(celery).dequeue()[0]
        assert item["api_key"] is None
        report = item["report"]
        position = report["position"]
        assert position["latitude"] == wifi.lat
        assert position["longitude"] == wifi.lon
        assert position["accuracy"] == 17.1
        assert "altitude" not in position
        assert "altitudeAccuracy" not in position
        assert "source" not in position
        wifis = report["wifiAccessPoints"]
        assert wifis[0]["macAddress"] == wifi.mac.upper()
        assert wifis[0]["age"] == 2500
        assert wifis[0]["channel"] == 1
        assert wifis[0]["frequency"] == 2437
        assert wifis[0]["signalStrength"] == -70
        assert wifis[0]["signalToNoiseRatio"] == 5
        assert wifis[0]["ssid"] == "my-wifi"

    def test_batches(self, app, celery):
        batch = self.queue(celery).batch + 10
        wifis = WifiShardFactory.build_batch(batch)
        items = [
            {"lat": wifi.lat, "lon": wifi.lon, "wifi": [{"key": wifi.mac}]}
            for wifi in wifis
        ]

        # add a bad one, this will just be skipped
        items.append({"lat": 10.0, "lon": 10.0, "whatever": "xx"})
        self._post(app, items)
        assert self.queue(celery).size() == batch

    def test_error_not_dict(self, app, celery, raven):
        wifi = WifiShardFactory.build()
        res = app.post_json(
            "/v1/submit", [{"lat": wifi.lat, "lon": wifi.lon, "cell": []}], status=400
        )
        detail = {
            "": (
                "\"[{'lat': 51.5, 'lon': -0.1, 'cell': []}]\" is not a mapping"
                " type: Does not implement dict-like functionality."
            )
        }
        assert res.json == ParseError({"validation": detail}).json_body()

    def test_error_missing_latlon(self, app, celery):
        wifi = WifiShardFactory.build()
        self._post(
            app,
            [
                {
                    "lat": wifi.lat,
                    "lon": wifi.lon,
                    "accuracy": 17.0,
                    "wifi": [{"key": wifi.mac}],
                },
                {"wifi": [{"key": wifi.mac}], "accuracy": 16.0},
                {"wifi": [{"key": wifi.mac}]},
            ],
        )
        assert self.queue(celery).size() == 3
