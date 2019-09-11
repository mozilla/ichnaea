import time
from unittest import mock

import boto3
import requests_mock
import simplejson

from ichnaea.data.export import DummyExporter, InternalTransform
from ichnaea.data.tasks import update_blue, update_cell, update_incoming, update_wifi
from ichnaea.models import BlueShard, CellShard, WifiShard
from ichnaea.tests.factories import (
    ApiKeyFactory,
    BlueShardFactory,
    CellShardFactory,
    ExportConfigFactory,
    WifiShardFactory,
)
from ichnaea import util


class BaseExportTest(object):
    def queue(self, celery):
        return celery.data_queues["update_incoming"]

    def add_reports(
        self,
        celery,
        num=1,
        blue_factor=0,
        cell_factor=1,
        wifi_factor=2,
        blue_key=None,
        cell_mcc=None,
        wifi_key=None,
        api_key="test",
        lat=None,
        lon=None,
        source=None,
    ):
        reports = []
        timestamp = int(time.time() * 1000)
        for i in range(num):
            pos = CellShardFactory.build()
            report = {
                "timestamp": timestamp,
                "position": {},
                "bluetoothBeacons": [],
                "cellTowers": [],
                "wifiAccessPoints": [],
            }
            report["position"]["latitude"] = lat or pos.lat
            report["position"]["longitude"] = lon or pos.lon
            report["position"]["accuracy"] = 17.0 + i
            if source is not None:
                report["position"]["source"] = source

            blues = BlueShardFactory.build_batch(blue_factor, lat=pos.lat, lon=pos.lon)
            for blue in blues:
                blue_data = {
                    "macAddress": blue_key or blue.mac,
                    "signalStrength": -100 + i,
                }
                report["bluetoothBeacons"].append(blue_data)

            cells = CellShardFactory.build_batch(cell_factor, lat=pos.lat, lon=pos.lon)
            for cell in cells:
                cell_data = {
                    "radioType": cell.radio.name,
                    "mobileCountryCode": cell_mcc or cell.mcc,
                    "mobileNetworkCode": cell.mnc,
                    "locationAreaCode": cell.lac,
                    "cellId": cell.cid,
                    "primaryScramblingCode": cell.psc,
                    "signalStrength": -110 + i,
                }
                report["cellTowers"].append(cell_data)

            wifis = WifiShardFactory.build_batch(wifi_factor, lat=pos.lat, lon=pos.lon)
            for wifi in wifis:
                wifi_data = {
                    "macAddress": wifi_key or wifi.mac,
                    "signalStrength": -90 + i,
                    "ssid": "my-wifi",
                }
                report["wifiAccessPoints"].append(wifi_data)

            reports.append(report)

        items = [
            {
                "api_key": api_key,
                "source": rep["position"].get("source", "gnss"),
                "report": rep,
            }
            for rep in reports
        ]

        self.queue(celery).enqueue(items)
        return reports

    def queue_length(self, redis, redis_key):
        return redis.llen(redis_key)


class TestExporter(BaseExportTest):
    def test_queues(self, celery, redis, session):
        ApiKeyFactory(valid_key="test2")
        ExportConfigFactory(
            name="test", batch=3, skip_keys=frozenset(["export_source"])
        )
        ExportConfigFactory(name="everything", batch=5)
        ExportConfigFactory(
            name="no_test", batch=2, skip_keys=frozenset(["test", "test_1"])
        )
        ExportConfigFactory(name="query", batch=2, skip_sources=frozenset(["gnss"]))
        session.flush()

        self.add_reports(celery, 4)
        self.add_reports(celery, 1, api_key="test2")
        self.add_reports(celery, 2, api_key=None, source="gnss")
        self.add_reports(celery, 1, api_key="test", source="query")
        update_incoming.delay().get()

        for queue_key, num in [
            ("queue_export_test", 2),
            ("queue_export_everything", 3),
            ("queue_export_no_test", 1),
            ("queue_export_query", 1),
        ]:
            assert self.queue_length(redis, queue_key) == num

    def test_retry(self, celery, redis, session):
        ExportConfigFactory(name="test", batch=1)
        session.flush()
        self.add_reports(celery, 1)

        num = [0]
        orig_wait = DummyExporter._retry_wait

        def mock_send(self, data, num=num):
            num[0] += 1
            if num[0] == 1:
                raise IOError()

        with mock.patch("ichnaea.data.export.DummyExporter.send", mock_send):
            try:
                DummyExporter._retry_wait = 0.001
                update_incoming.delay().get()
            finally:
                DummyExporter._retry_wait = orig_wait

        assert self.queue_length(redis, "queue_export_test") == 0


class TestGeosubmit(BaseExportTest):
    def test_upload(self, celery, session, stats):
        ApiKeyFactory(valid_key="e5444-794")
        ExportConfigFactory(
            name="test",
            batch=3,
            schema="geosubmit",
            url="http://127.0.0.1:9/v2/geosubmit?key=external",
        )
        session.flush()

        reports = []
        reports.extend(self.add_reports(celery, 1, source="gnss"))
        reports.extend(self.add_reports(celery, 1, api_key="e5444e9f-7946"))
        reports.extend(self.add_reports(celery, 1, api_key=None, source="fused"))

        with requests_mock.Mocker() as mock:
            mock.register_uri("POST", requests_mock.ANY, text="{}")
            update_incoming.delay().get()

        assert mock.call_count == 1
        req = mock.request_history[0]

        # check headers
        assert req.headers["Content-Type"] == "application/json"
        assert req.headers["Content-Encoding"] == "gzip"
        assert req.headers["User-Agent"] == "ichnaea"

        body = util.decode_gzip(req.body)
        send_reports = simplejson.loads(body)["items"]
        assert len(send_reports) == 3

        for field in ("accuracy", "source", "timestamp"):
            expect = [report["position"].get(field) for report in reports]
            gotten = [report["position"].get(field) for report in send_reports]
            assert set(expect) == set(gotten)

        assert set([w["ssid"] for w in send_reports[0]["wifiAccessPoints"]]) == set(
            ["my-wifi"]
        )

        stats.check(
            counter=[
                ("data.export.batch", 1, 1, ["key:test"]),
                ("data.export.upload", 1, ["key:test", "status:200"]),
            ],
            timer=[("data.export.upload", ["key:test"])],
        )


class TestS3(BaseExportTest):
    def test_upload(self, celery, session, stats):
        ExportConfigFactory(
            name="backup",
            batch=3,
            schema="s3",
            url="s3://bucket/backups/{source}/{api_key}/{year}/{month}/{day}",
        )
        ApiKeyFactory(valid_key="e5444-794")
        session.flush()

        reports = self.add_reports(celery, 3)
        self.add_reports(celery, 3, api_key="e5444-794", source="gnss")
        self.add_reports(celery, 3, api_key="e5444-794", source="fused")
        self.add_reports(celery, 3, api_key=None)

        mock_conn = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_obj = mock.MagicMock()
        mock_conn.return_value.Bucket.return_value = mock_bucket
        mock_bucket.Object.return_value = mock_obj

        with mock.patch.object(boto3, "resource", mock_conn):
            update_incoming.delay().get()

        obj_calls = mock_bucket.Object.call_args_list
        put_calls = mock_obj.put.call_args_list
        assert len(obj_calls) == 4
        assert len(put_calls) == 4

        keys = []
        test_export = None
        for obj_call, put_call in zip(obj_calls, put_calls):
            s3_key = obj_call[0][0]
            assert s3_key.startswith("backups/")
            assert s3_key.endswith(".json.gz")
            assert put_call[1]["Body"]
            assert put_call[1]["ContentType"] == "application/json"
            assert put_call[1]["ContentEncoding"] == "gzip"
            keys.append(s3_key)
            if "test" in s3_key:
                test_export = put_call[1]["Body"]

        # extract second and third path segment from key names
        groups = [tuple(key.split("/")[1:3]) for key in keys]
        assert set(groups) == set(
            [
                ("gnss", "test"),
                ("gnss", "no_key"),
                ("gnss", "e5444-794"),
                ("fused", "e5444-794"),
            ]
        )

        # check uploaded content
        uploaded_text = util.decode_gzip(test_export)

        send_reports = simplejson.loads(uploaded_text)["items"]
        assert len(send_reports) == 3
        expect = [report["position"]["accuracy"] for report in reports]
        gotten = [report["position"]["accuracy"] for report in send_reports]
        assert set(expect) == set(gotten)

        stats.check(
            counter=[
                ("data.export.batch", 4, 1, ["key:backup"]),
                ("data.export.upload", 4, ["key:backup", "status:success"]),
            ],
            timer=[("data.export.upload", 4, ["key:backup"])],
        )


class TestInternalTransform(object):

    transform = InternalTransform()

    def test_empty(self):
        assert self.transform({}) == {}

    def test_position(self):
        timestamp = int(time.time() * 1000)
        assert self.transform(
            {
                "position": {
                    "latitude": 1.0,
                    "longitude": 2.0,
                    "accuracy": 30.1,
                    "altitude": 1100.3,
                    "altitudeAccuracy": 50.7,
                    "age": 6001,
                    "heading": 270.1,
                    "speed": 2.5,
                    "pressure": 1020.2,
                    "source": "gnss",
                },
                "timestamp": timestamp,
                "wifiAccessPoints": [{"macAddress": "abcdef123456"}],
            }
        ) == {
            "lat": 1.0,
            "lon": 2.0,
            "accuracy": 30.1,
            "altitude": 1100.3,
            "altitude_accuracy": 50.7,
            "heading": 270.1,
            "speed": 2.5,
            "pressure": 1020.2,
            "source": "gnss",
            "timestamp": timestamp - 6001,
            "wifi": [{"mac": "abcdef123456", "age": -6001}],
        }

    def test_age(self):
        assert self.transform(
            {
                "position": {"age": 1000},
                "bluetoothBeacons": [{"age": 2000}, {"macAddress": "ab"}],
                "wifiAccessPoints": [{"age": -500}, {"age": 1500}],
            }
        ) == {
            "blue": [{"age": 1000}, {"age": -1000, "mac": "ab"}],
            "wifi": [{"age": -1500}, {"age": 500}],
        }

    def test_timestamp(self):
        assert self.transform(
            {
                "timestamp": 1460700010000,
                "position": {"age": 2000},
                "bluetoothBeacons": [{"age": -3000}, {"macAddress": "ab"}],
                "cellTowers": [{"age": 3000}, {"radioType": "gsm"}],
                "wifiAccessPoints": [{"age": 1500}, {"age": -2500}],
            }
        ) == {
            "timestamp": 1460700008000,
            "blue": [{"age": -5000}, {"mac": "ab", "age": -2000}],
            "cell": [{"age": 1000}, {"radio": "gsm", "age": -2000}],
            "wifi": [{"age": -500}, {"age": -4500}],
        }

    def test_blue(self):
        assert self.transform(
            {
                "bluetoothBeacons": [
                    {"macAddress": "abcdef123456", "age": 3001, "signalStrength": -90}
                ]
            }
        ) == {"blue": [{"mac": "abcdef123456", "age": 3001, "signal": -90}]}

    def test_cell(self):
        assert self.transform(
            {
                "cellTowers": [
                    {
                        "radioType": "gsm",
                        "mobileCountryCode": 262,
                        "mobileNetworkCode": 1,
                        "locationAreaCode": 123,
                        "cellId": 4567,
                        "age": 3001,
                        "asu": 15,
                        "primaryScramblingCode": 120,
                        "serving": 1,
                        "signalStrength": -90,
                        "timingAdvance": 10,
                    }
                ]
            }
        ) == {
            "cell": [
                {
                    "radio": "gsm",
                    "mcc": 262,
                    "mnc": 1,
                    "lac": 123,
                    "cid": 4567,
                    "age": 3001,
                    "asu": 15,
                    "psc": 120,
                    "serving": 1,
                    "signal": -90,
                    "ta": 10,
                }
            ]
        }

    def test_wifi(self):
        assert self.transform(
            {
                "wifiAccessPoints": [
                    {
                        "macAddress": "abcdef123456",
                        "age": 3001,
                        "channel": 1,
                        "frequency": 2412,
                        "radioType": "802.11ac",
                        "signalToNoiseRatio": 80,
                        "signalStrength": -90,
                    }
                ]
            }
        ) == {
            "wifi": [
                {
                    "mac": "abcdef123456",
                    "age": 3001,
                    "channel": 1,
                    "frequency": 2412,
                    "radio": "802.11ac",
                    "snr": 80,
                    "signal": -90,
                }
            ]
        }


class TestInternal(BaseExportTest):
    def _pop_item(self, celery):
        return self.queue(celery).dequeue()[0]

    def _push_item(self, celery, item):
        self.queue(celery).enqueue([item])

    def _update_all(self, session, datamap_only=False):
        ExportConfigFactory(name="internal", batch=0, schema="internal")
        session.flush()
        update_incoming.delay().get()

        if datamap_only:
            return

        for shard_id in BlueShard.shards().keys():
            update_blue.delay(shard_id=shard_id).get()

        for shard_id in CellShard.shards().keys():
            update_cell.delay(shard_id=shard_id).get()

        for shard_id in WifiShard.shards().keys():
            update_wifi.delay(shard_id=shard_id).get()

    def test_stats(self, celery, session, stats):
        ApiKeyFactory(valid_key="e5444-794")
        session.flush()

        self.add_reports(celery, 3)
        self.add_reports(celery, 3, api_key="e5444-794", source="gnss")
        self.add_reports(celery, 3, api_key="e5444-794", source="fused")
        self.add_reports(celery, 3, api_key=None)
        self._update_all(session)

        stats.check(
            counter=[
                ("data.export.batch", 1, 1, ["key:internal"]),
                ("data.report.upload", 2, 3),
                ("data.report.upload", 1, 3, ["key:test"]),
                ("data.report.upload", 1, 6, ["key:e5444-794"]),
                ("data.observation.upload", 1, 3, ["type:cell", "key:test"]),
                ("data.observation.upload", 1, 6, ["type:wifi", "key:test"]),
                ("data.observation.upload", 0, ["type:cell", "key:no_key"]),
                ("data.observation.upload", 1, 6, ["type:cell", "key:e5444-794"]),
                ("data.observation.upload", 1, 12, ["type:wifi", "key:e5444-794"]),
            ]
        )
        # we get a variable number of statsd messages and are only
        # interested in the sum-total
        for name, total in (("cell", 12), ("wifi", 24)):
            insert_msgs = [
                msg
                for msg in stats.msgs
                if (msg.startswith("data.observation.insert") and "type:" + name in msg)
            ]
            assert (
                sum([int(msg.split(":")[1].split("|")[0]) for msg in insert_msgs])
                == total
            )

    def test_blue(self, celery, session):
        reports = self.add_reports(celery, blue_factor=1, cell_factor=0, wifi_factor=0)
        self._update_all(session)

        position = reports[0]["position"]
        blue_data = reports[0]["bluetoothBeacons"][0]
        shard = BlueShard.shard_model(blue_data["macAddress"])
        blues = session.query(shard).all()
        assert len(blues) == 1
        blue = blues[0]
        assert blue.lat == position["latitude"]
        assert blue.lon == position["longitude"]
        assert blue.mac == blue_data["macAddress"]
        assert blue.samples == 1

    def test_blue_duplicated(self, celery, session):
        self.add_reports(celery, blue_factor=1, cell_factor=0, wifi_factor=0)
        # duplicate the Bluetooth entry inside the report
        item = self._pop_item(celery)
        report = item["report"]
        blue = report["bluetoothBeacons"][0]
        mac = blue["macAddress"]
        report["bluetoothBeacons"].append(blue.copy())
        report["bluetoothBeacons"].append(blue.copy())
        report["bluetoothBeacons"][1]["signalStrength"] += 2
        report["bluetoothBeacons"][2]["signalStrength"] -= 2
        self._push_item(celery, item)
        self._update_all(session)

        shard = BlueShard.shard_model(mac)
        blues = session.query(shard).all()
        assert len(blues) == 1
        assert blues[0].samples == 1

    def test_bluetooth_invalid(self, celery, session):
        self.add_reports(
            celery, blue_factor=1, cell_factor=0, wifi_factor=0, blue_key="abcd"
        )
        self._update_all(session)

    def test_cell(self, celery, session):
        reports = self.add_reports(celery, cell_factor=1, wifi_factor=0)
        self._update_all(session)

        position = reports[0]["position"]
        cell_data = reports[0]["cellTowers"][0]
        shard = CellShard.shard_model(cell_data["radioType"])
        cells = session.query(shard).all()
        assert len(cells) == 1
        cell = cells[0]

        assert cell.lat == position["latitude"]
        assert cell.lon == position["longitude"]
        assert cell.radio.name == cell_data["radioType"]
        assert cell.mcc == cell_data["mobileCountryCode"]
        assert cell.mnc == cell_data["mobileNetworkCode"]
        assert cell.lac == cell_data["locationAreaCode"]
        assert cell.cid == cell_data["cellId"]
        assert cell.psc == cell_data["primaryScramblingCode"]
        assert cell.samples == 1

    def test_cell_duplicated(self, celery, session):
        self.add_reports(celery, cell_factor=1, wifi_factor=0)
        # duplicate the cell entry inside the report
        item = self._pop_item(celery)
        report = item["report"]
        cell = report["cellTowers"][0]
        radio = cell["radioType"]
        report["cellTowers"].append(cell.copy())
        report["cellTowers"].append(cell.copy())
        report["cellTowers"][1]["signalStrength"] += 2
        report["cellTowers"][2]["signalStrength"] -= 2
        self._push_item(celery, item)
        self._update_all(session)

        shard = CellShard.shard_model(radio)
        cells = session.query(shard).all()
        assert len(cells) == 1
        assert cells[0].samples == 1

    def test_cell_invalid(self, celery, session, stats):
        self.add_reports(celery, cell_factor=1, wifi_factor=0, cell_mcc=-2)
        self._update_all(session)

        stats.check(
            counter=[
                ("data.report.upload", 1, 1, ["key:test"]),
                ("data.report.drop", 1, 1, ["key:test"]),
                ("data.observation.drop", 1, 1, ["type:cell", "key:test"]),
            ]
        )

    def test_wifi(self, celery, session):
        reports = self.add_reports(celery, cell_factor=0, wifi_factor=1)
        self._update_all(session)

        position = reports[0]["position"]
        wifi_data = reports[0]["wifiAccessPoints"][0]
        shard = WifiShard.shard_model(wifi_data["macAddress"])
        wifis = session.query(shard).all()
        assert len(wifis) == 1
        wifi = wifis[0]
        assert wifi.lat == position["latitude"]
        assert wifi.lon == position["longitude"]
        assert wifi.mac == wifi_data["macAddress"]
        assert wifi.samples == 1

    def test_wifi_duplicated(self, celery, session):
        self.add_reports(celery, cell_factor=0, wifi_factor=1)
        # duplicate the wifi entry inside the report
        item = self._pop_item(celery)
        report = item["report"]
        wifi = report["wifiAccessPoints"][0]
        mac = wifi["macAddress"]
        report["wifiAccessPoints"].append(wifi.copy())
        report["wifiAccessPoints"].append(wifi.copy())
        report["wifiAccessPoints"][1]["signalStrength"] += 2
        report["wifiAccessPoints"][2]["signalStrength"] -= 2
        self._push_item(celery, item)
        self._update_all(session)

        shard = WifiShard.shard_model(mac)
        wifis = session.query(shard).all()
        assert len(wifis) == 1
        assert wifis[0].samples == 1

    def test_wifi_invalid(self, celery, session, stats):
        self.add_reports(celery, cell_factor=0, wifi_factor=1, wifi_key="abcd")
        self._update_all(session)

        stats.check(
            counter=[
                ("data.report.upload", 1, 1, ["key:test"]),
                ("data.report.drop", 1, 1, ["key:test"]),
                ("data.observation.drop", 1, 1, ["type:wifi", "key:test"]),
            ]
        )

    def test_position_invalid(self, celery, session, stats):
        self.add_reports(
            celery, 1, cell_factor=0, wifi_factor=1, wifi_key="000000123456", lat=-90.1
        )
        self.add_reports(
            celery, 1, cell_factor=0, wifi_factor=1, wifi_key="000000234567"
        )
        self._update_all(session)

        shard = WifiShard.shards()["0"]
        assert session.query(shard).count() == 1
        stats.check(
            counter=[
                ("data.report.upload", 1, 2, ["key:test"]),
                ("data.report.drop", 1, 1, ["key:test"]),
                ("data.observation.insert", 1, 1, ["type:wifi"]),
                ("data.observation.upload", 1, 1, ["type:wifi", "key:test"]),
            ]
        )

    def test_no_observations(self, celery, session):
        self.add_reports(celery, 1, cell_factor=0, wifi_factor=0)
        self._update_all(session)

    def test_datamap(self, celery, session):
        self.add_reports(celery, 1, cell_factor=0, wifi_factor=2, lat=50.0, lon=10.0)
        self.add_reports(celery, 2, cell_factor=0, wifi_factor=2, lat=20.0, lon=-10.0)
        self._update_all(session, datamap_only=True)
        assert celery.data_queues["update_datamap_ne"].size() == 1
        assert celery.data_queues["update_datamap_sw"].size() == 1
