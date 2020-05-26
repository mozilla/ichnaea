import time

import colander
import pytest

from ichnaea.models import Radio
from ichnaea.api.submit.schema_v2 import SUBMIT_V2_SCHEMA
from ichnaea.api.submit.tests.base import BaseSubmitTest
from ichnaea.tests.factories import BlueShardFactory, CellShardFactory, WifiShardFactory


class TestSubmitSchema(object):
    def test_empty(self):
        with pytest.raises(colander.Invalid):
            SUBMIT_V2_SCHEMA.deserialize({})

    def test_timestamp(self):
        wifi = WifiShardFactory.build()

        data = SUBMIT_V2_SCHEMA.deserialize(
            {
                "items": [
                    {
                        "timestamp": 146 * 10 ** 10,
                        "wifiAccessPoints": [{"macAddress": wifi.mac}],
                    }
                ]
            }
        )
        assert data["items"][0]["timestamp"] == 146 * 10 ** 10

        data = SUBMIT_V2_SCHEMA.deserialize(
            {
                "items": [
                    {
                        "timestamp": 146 * 10 ** 9,
                        "wifiAccessPoints": [{"macAddress": wifi.mac}],
                    }
                ]
            }
        )
        # value was discarded and replaced by 'now'
        assert data["items"][0]["timestamp"] > 10 ** 12


class TestView(BaseSubmitTest):

    url = "/v2/geosubmit"
    metric_path = "path:v2.geosubmit"
    status = 200
    radio_id = "radioType"
    cells_id = "cellTowers"

    def _one_cell_query(self, radio=True):
        cell = CellShardFactory.build()
        query = {
            "position": {"latitude": cell.lat, "longitude": cell.lon},
            "cellTowers": [
                {
                    "mobileCountryCode": cell.mcc,
                    "mobileNetworkCode": cell.mnc,
                    "locationAreaCode": cell.lac,
                    "cellId": cell.cid,
                }
            ],
        }
        if radio:
            query["cellTowers"][0]["radioType"] = cell.radio.name
        return (cell, query)

    def test_bluetooth(self, app, celery):
        blue = BlueShardFactory.build()
        self._post(
            app,
            [
                {
                    "position": {"latitude": blue.lat, "longitude": blue.lon},
                    "bluetoothBeacons": [
                        {
                            "macAddress": blue.mac,
                            "name": "my-beacon",
                            "age": 3,
                            "signalStrength": -90,
                            "xtra_field": 4,
                        },
                        {"name": "beacon-2", "signalStrength": -92},
                    ],
                    "wifiAccessPoints": [{"signalStrength": -52}],
                }
            ],
        )

        assert self.queue(celery).size() == 1
        item = self.queue(celery).dequeue()[0]
        report = item["report"]
        assert "timestamp" in report
        position = report["position"]
        assert position["latitude"] == blue.lat
        assert position["longitude"] == blue.lon
        blues = report["bluetoothBeacons"]
        assert len(blues) == 1
        assert blues[0]["macAddress"] == blue.mac
        assert blues[0]["age"] == 3
        assert blues[0]["name"] == "my-beacon"
        assert blues[0]["signalStrength"] == -90
        assert "xtra_field" not in blues[0]
        wifis = report["wifiAccessPoints"]
        assert len(wifis) == 0

    def test_cell(self, app, celery):
        now_ms = int(time.time() * 1000)
        cell = CellShardFactory.build(radio=Radio.wcdma)
        response = self._post(
            app,
            [
                {
                    "carrier": "Some Carrier",
                    "homeMobileCountryCode": cell.mcc,
                    "homeMobileNetworkCode": cell.mnc,
                    "timestamp": now_ms,
                    "xtra_field": 1,
                    "position": {
                        "latitude": cell.lat,
                        "longitude": cell.lon,
                        "accuracy": 12.4,
                        "altitude": 100.1,
                        "altitudeAccuracy": 23.7,
                        "age": 1,
                        "heading": 45.0,
                        "pressure": 1013.25,
                        "source": "fused",
                        "speed": 3.6,
                        "xtra_field": 2,
                    },
                    "cellTowers": [
                        {
                            "radioType": "umts",
                            "mobileCountryCode": cell.mcc,
                            "mobileNetworkCode": cell.mnc,
                            "locationAreaCode": cell.lac,
                            "cellId": cell.cid,
                            "primaryScramblingCode": cell.psc,
                            "age": 3,
                            "asu": 31,
                            "serving": 1,
                            "signalStrength": -51,
                            "timingAdvance": 1,
                            "xtra_field": 3,
                        }
                    ],
                }
            ],
            api_key="test",
        )
        # check that we get an empty response
        assert response.content_type == "application/json"
        assert response.json == {}

        assert self.queue(celery).size() == 1
        item = self.queue(celery).dequeue()[0]
        assert item["api_key"] == "test"
        report = item["report"]
        assert report["timestamp"] == now_ms
        assert report["carrier"] == "Some Carrier"
        assert report["homeMobileCountryCode"] == cell.mcc
        assert report["homeMobileNetworkCode"] == cell.mnc
        assert "xtra_field" not in report
        position = report["position"]
        assert position["latitude"] == cell.lat
        assert position["longitude"] == cell.lon
        assert position["accuracy"] == 12.4
        assert position["age"] == 1
        assert position["altitude"] == 100.1
        assert position["altitudeAccuracy"] == 23.7
        assert position["heading"] == 45.0
        assert position["pressure"] == 1013.25
        assert position["source"] == "fused"
        assert position["speed"] == 3.6
        assert "xtra_field" not in position
        cells = report["cellTowers"]
        assert len(cells) == 1
        assert cells[0]["radioType"] == "wcdma"
        assert cells[0]["mobileCountryCode"] == cell.mcc
        assert cells[0]["mobileNetworkCode"] == cell.mnc
        assert cells[0]["locationAreaCode"] == cell.lac
        assert cells[0]["cellId"] == cell.cid
        assert cells[0]["primaryScramblingCode"] == cell.psc
        assert cells[0]["age"] == 3
        assert cells[0]["asu"] == 31
        assert cells[0]["serving"] == 1
        assert cells[0]["signalStrength"] == -51
        assert cells[0]["timingAdvance"] == 1
        assert "xtra_field" not in cells[0]

    def test_wifi(self, app, celery):
        wifi = WifiShardFactory.build()
        self._post(
            app,
            [
                {
                    "position": {"latitude": wifi.lat, "longitude": wifi.lon},
                    "wifiAccessPoints": [
                        {
                            "macAddress": wifi.mac,
                            "ssid": "my-wifi",
                            "age": 3,
                            "channel": 5,
                            "frequency": 2437,
                            "radioType": "802.11n",
                            "signalStrength": -90,
                            "signalToNoiseRatio": 5,
                            "ssid": "my-wifi",
                            "xtra_field": 3,
                        }
                    ],
                }
            ],
        )

        assert self.queue(celery).size() == 1
        item = self.queue(celery).dequeue()[0]
        assert item["api_key"] is None
        report = item["report"]
        assert "timestamp" in report
        position = report["position"]
        assert position["latitude"] == wifi.lat
        assert position["longitude"] == wifi.lon
        wifis = item["report"]["wifiAccessPoints"]
        assert len(wifis) == 1
        assert wifis[0]["macAddress"] == wifi.mac
        assert wifis[0]["age"] == 3
        assert wifis[0]["channel"] == 5
        assert wifis[0]["frequency"] == 2437
        assert wifis[0]["radioType"] == "802.11n"
        assert wifis[0]["signalStrength"] == -90
        assert wifis[0]["signalToNoiseRatio"] == 5
        assert wifis[0]["ssid"] == "my-wifi"
        assert "xtra_field" not in wifis[0]

    def test_batches(self, app, celery):
        batch = self.queue(celery).batch + 10
        wifis = WifiShardFactory.build_batch(batch)
        items = [
            {
                "position": {"latitude": wifi.lat, "longitude": wifi.lon},
                "wifiAccessPoints": [{"macAddress": wifi.mac}],
            }
            for wifi in wifis
        ]

        # add a bad one, this will just be skipped
        items.append({"latitude": 10.0, "longitude": 10.0, "whatever": "xx"})
        self._post(app, items)
        assert self.queue(celery).size() == batch

    def test_error(self, app, celery, raven):
        wifi = WifiShardFactory.build()
        response = self._post(
            app,
            [
                {
                    "position": {"latitude": wifi.lat, "longitude": wifi.lon},
                    "wifiAccessPoints": [{"macAddress": 10}],
                }
            ],
            status=400,
        )
        assert response.json["details"]["validation"] == {
            "items.0.wifiAccessPoints.0.macAddress": (
                "10 is not a string: {'macAddress': ''}"
            )
        }
        assert self.queue(celery).size() == 0

    def test_error_missing_latlon(self, app, celery):
        wifi = WifiShardFactory.build()
        self._post(
            app,
            [
                {
                    "position": {
                        "latitude": wifi.lat,
                        "longitude": wifi.lon,
                        "accuracy": 17.0,
                    },
                    "wifiAccessPoints": [{"macAddress": wifi.mac}],
                },
                {
                    "position": {"accuracy": 16.0},
                    "wifiAccessPoints": [{"macAddress": wifi.mac}],
                },
                {"wifiAccessPoints": [{"macAddress": wifi.mac}]},
            ],
        )
        assert self.queue(celery).size() == 3
        item1, item2, item3 = self.queue(celery).dequeue()
        assert set(item1["report"]["position"].keys()) == {
            "latitude",
            "longitude",
            "accuracy",
        }
        assert set(item2["report"]["position"].keys()) == {"accuracy"}
        assert "position" not in item3["report"]
