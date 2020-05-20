import json
import operator

import pytest
import requests_mock

from ichnaea.api.exceptions import (
    DailyLimitExceeded,
    InvalidAPIKey,
    LocationNotFound,
    ParseError,
)
from ichnaea.api.locate.constants import (
    BLUE_MIN_ACCURACY,
    BLUE_MAX_ACCURACY,
    CELL_MIN_ACCURACY,
    CELL_MAX_ACCURACY,
    CELLAREA_MIN_ACCURACY,
    CELLAREA_MAX_ACCURACY,
    WIFI_MIN_ACCURACY,
    WIFI_MAX_ACCURACY,
)
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import Position, Region
from ichnaea.conftest import GEOIP_DATA
from ichnaea.models import BlueShard, CellArea, CellShard, WifiShard, Radio
from ichnaea.tests.factories import (
    ApiKeyFactory,
    BlueShardFactory,
    CellAreaFactory,
    CellShardFactory,
    KeyFactory,
    WifiShardFactory,
)
from ichnaea import util

_sentinel = object()


class DummyModel(object):
    def __init__(self, lat=None, lon=None, radius=None, code=None, name=None, ip=None):
        self.lat = lat
        self.lon = lon
        self.radius = radius
        self.code = code
        self.name = name
        self.ip = ip


def bound_model_accuracy(model, accuracy):
    if isinstance(model, BlueShard):
        accuracy = min(max(accuracy, BLUE_MIN_ACCURACY), BLUE_MAX_ACCURACY)
    elif isinstance(model, CellShard):
        accuracy = min(max(accuracy, CELL_MIN_ACCURACY), CELL_MAX_ACCURACY)
    elif isinstance(model, CellArea):
        accuracy = min(max(accuracy, CELLAREA_MIN_ACCURACY), CELLAREA_MAX_ACCURACY)
    elif isinstance(model, WifiShard):
        accuracy = min(max(accuracy, WIFI_MIN_ACCURACY), WIFI_MAX_ACCURACY)
    return accuracy


class BaseSourceTest(object):

    api_key = KeyFactory(valid_key="test", allow_fallback=True)
    api_type = "locate"
    Source = None

    def make_query(self, geoip_db, http_session, session, **kw):
        api_key = kw.pop("api_key", self.api_key)

        return Query(
            api_key=api_key,
            api_type=self.api_type,
            session=session,
            http_session=http_session,
            geoip_db=geoip_db,
            **kw,
        )

    def model_query(
        self, geoip_db, http_session, session, blues=(), cells=(), wifis=(), **kw
    ):
        query_blue = []
        if blues:
            for blue in blues:
                query_blue.append({"macAddress": blue.mac})

        query_cell = []
        if cells:
            for cell in cells:
                cell_query = {
                    "radioType": cell.radio,
                    "mobileCountryCode": cell.mcc,
                    "mobileNetworkCode": cell.mnc,
                    "locationAreaCode": cell.lac,
                }
                if getattr(cell, "cid", None) is not None:
                    cell_query["cellId"] = cell.cid
                query_cell.append(cell_query)

        query_wifi = []
        if wifis:
            for wifi in wifis:
                query_wifi.append({"macAddress": wifi.mac})

        return self.make_query(
            geoip_db,
            http_session,
            session,
            blue=query_blue,
            cell=query_cell,
            wifi=query_wifi,
            **kw,
        )

    def check_should_search(self, source, query, should, results=None):
        if results is None:
            results = source.result_list()
        assert source.should_search(query, results) is should

    def check_model_results(self, results, models, **kw):
        type_ = self.Source.result_type

        if not models:
            assert len(results) == 0
            return

        expected = []
        if type_ is Position:
            for model in models:
                expected.append(
                    {
                        "lat": kw.get("lat", model.lat),
                        "lon": kw.get("lon", model.lon),
                        "accuracy": bound_model_accuracy(
                            model, kw.get("accuracy", model.radius)
                        ),
                    }
                )

            # don't test ordering of results
            expected = sorted(expected, key=operator.itemgetter("lat", "lon"))
            results = sorted(results, key=operator.attrgetter("lat", "lon"))

        elif type_ is Region:
            for model in models:
                expected.append({"region_code": model.code, "region_name": model.name})
            # don't test ordering of results
            expected = sorted(expected, key=operator.itemgetter("region_code"))
            results = sorted(results, key=operator.attrgetter("region_code"))

        for expect, result in zip(expected, results):
            assert type(result) is type_
            for key, value in expect.items():
                assert getattr(result, key) == value


class BaseLocateTest(object):

    url = None
    apikey_metrics = True
    metric_path = None
    metric_type = None
    not_found = LocationNotFound
    test_ip = GEOIP_DATA["London"]["ip"]

    @property
    def ip_response(self):
        return {}

    def _call(
        self,
        app,
        body=None,
        api_key=_sentinel,
        ip=None,
        status=200,
        headers=None,
        method="post_json",
        **kw,
    ):
        if body is None:
            body = {}
        url = self.url
        if api_key:
            if api_key is _sentinel:
                api_key = "test"
            url += "?key=%s" % api_key
        extra_environ = {}
        if ip is not None:
            extra_environ = {"HTTP_X_FORWARDED_FOR": ip}
        call = getattr(app, method)
        if method in ("get", "delete", "head", "options"):
            return call(
                url, extra_environ=extra_environ, status=status, headers=headers, **kw
            )
        else:
            return call(
                url,
                body,
                content_type="application/json",
                extra_environ=extra_environ,
                status=status,
                headers=headers,
                **kw,
            )

    def check_queue(self, data_queues, num):
        assert data_queues["update_incoming"].size() == num

    def check_response(
        self, data_queues, response, status, fallback=None, details=None
    ):
        assert response.content_type == "application/json"
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        assert response.headers["Access-Control-Max-Age"] == "2592000"
        if status == "ok":
            body = dict(response.json)
            if fallback:
                assert body["fallback"] == fallback
                del body["fallback"]
            assert body == self.ip_response
        elif status == "invalid_key":
            assert response.json == InvalidAPIKey().json_body()
        elif status == "not_found":
            assert response.json == self.not_found().json_body()
        elif status == "parse_error":
            assert response.json == ParseError(details).json_body()
        elif status == "limit_exceeded":
            assert response.json == DailyLimitExceeded().json_body()
        if status != "ok":
            self.check_queue(data_queues, 0)

    def check_model_response(
        self, response, model, region=None, fallback=None, expected_names=(), **kw
    ):
        expected = {"region": region}
        for name in ("lat", "lon", "accuracy"):
            if name in kw:
                expected[name] = kw[name]
            else:
                model_name = name
                if name == "accuracy":
                    expected[name] = bound_model_accuracy(
                        model, getattr(model, "radius")
                    )
                else:
                    expected[name] = getattr(model, model_name)

        if fallback is not None:
            expected_names = set(expected_names).union(set(["fallback"]))

        assert response.content_type == "application/json"
        assert set(response.json.keys()) == expected_names

        return expected

    def model_query(self, blues=(), cells=(), wifis=()):
        query = {}
        if blues:
            query["bluetoothBeacons"] = []
            for blue in blues:
                query["bluetoothBeacons"].append({"macAddress": blue.mac})
        if cells:
            query["cellTowers"] = []
            for cell in cells:
                radio_name = cell.radio.name
                radio_name = "wcdma" if radio_name == "umts" else radio_name
                cell_query = {
                    "radioType": radio_name,
                    "mobileCountryCode": cell.mcc,
                    "mobileNetworkCode": cell.mnc,
                    "locationAreaCode": cell.lac,
                }
                if getattr(cell, "cid", None) is not None:
                    cell_query["cellId"] = cell.cid
                if getattr(cell, "psc", None) is not None:
                    cell_query["primaryScramblingCode"] = cell.psc
                query["cellTowers"].append(cell_query)
        if wifis:
            query["wifiAccessPoints"] = []
            for wifi in wifis:
                query["wifiAccessPoints"].append({"macAddress": wifi.mac})
        return query


class CommonLocateTest(BaseLocateTest):
    """Common tests for geolocate and region APIs."""

    def test_get(self, app, data_queues, metricsmock):
        """A GET returns an IP-based location."""
        res = self._call(app, ip=self.test_ip, method="get", status=200)
        self.check_response(data_queues, res, "ok")
        self.check_queue(data_queues, 0)

        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:get", "status:200"]
        )
        metricsmock.assert_timing_once(
            "request.timing", tags=[self.metric_path, "method:get"]
        )

    def test_options(self, app):
        """An OPTIONS request works, as required for CORS"""
        res = self._call(app, method="options", status=200)
        assert res.headers["Access-Control-Allow-Origin"] == "*"
        assert res.headers["Access-Control-Max-Age"] == "2592000"

    @pytest.mark.parametrize("method", ("delete", "patch", "put"))
    def test_unsupported_methods(self, app, method):
        """Other HTTP methods are not allowed, and are not logged by app."""
        self._call(app, method=method, status=405)

    def test_empty_body(self, app, data_queues, redis):
        """A POST with an empty body returns an IP-based lookup."""
        res = self._call(app, "", ip=self.test_ip, method="post", status=200)
        self.check_response(data_queues, res, "ok")
        self.check_queue(data_queues, 0)
        if self.apikey_metrics:
            # ensure that a apiuser hyperloglog entry was added for today
            today = util.utcnow().date().strftime("%Y-%m-%d")
            expected = "apiuser:%s:test:%s" % (self.metric_type, today)
            assert [key.decode("ascii") for key in redis.keys("apiuser:*")] == [
                expected
            ]
            # check that the ttl was set
            ttl = redis.ttl(expected)
            assert 7 * 24 * 3600 < ttl <= 8 * 24 * 3600

    def test_empty_json(self, app, data_queues, metricsmock):
        """A POST with empty JSON returns an IP-based lookup."""
        res = self._call(app, ip=self.test_ip, status=200)
        self.check_response(data_queues, res, "ok")
        self.check_queue(data_queues, 0)

        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:200"]
        )
        metricsmock.assert_timing_once(
            "request.timing", tags=[self.metric_path, "method:post"]
        )
        if self.apikey_metrics:
            metricsmock.assert_incr_once(
                self.metric_type + ".query",
                tags=["key:test", "blue:none", "cell:none", "wifi:none"],
            )
            metricsmock.assert_incr_once(
                self.metric_type + ".result",
                tags=[
                    "key:test",
                    "fallback_allowed:false",
                    "accuracy:low",
                    "status:hit",
                    "source:geoip",
                ],
            )
            metricsmock.assert_incr_once(
                self.metric_type + ".source",
                tags=["key:test", "source:geoip", "accuracy:low", "status:hit"],
            )

    def test_error_no_json(self, app, data_queues, metricsmock):
        """A POST with invalid JSON is an error."""
        res = self._call(app, "\xae", method="post", status=400)
        detail = "JSONDecodeError('Expecting value: line 1 column 1 (char 0)')"
        self.check_response(data_queues, res, "parse_error", details={"decode": detail})
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )

    def test_error_no_mapping(self, app, data_queues):
        """A POST with list JSON is an error."""
        res = self._call(app, [1], status=400)
        detail = {
            "": (
                '"[1]" is not a mapping type: Does not implement dict-like'
                " functionality."
            )
        }
        self.check_response(
            data_queues, res, "parse_error", details={"validation": detail}
        )

    def test_invalid_data_is_empty(self, app, data_queues):
        """POST data with bad keys looks like empty data after sanitization."""
        res = self._call(app, {"invalid": 0}, ip=self.test_ip, status=200)
        self.check_response(data_queues, res, "ok")
        self.check_queue(data_queues, 0)

    def test_no_api_key(self, app, data_queues, redis, metricsmock):
        """Omitting the API key is a 400 error."""
        res = self._call(app, api_key=None, ip=self.test_ip, status=400)
        self.check_response(data_queues, res, "invalid_key")
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:none"]
        )
        assert redis.keys("apiuser:*") == []

    def test_invalid_api_key(self, app, data_queues, redis, metricsmock):
        """An invalid API key is sanitized to the same as no key."""
        res = self._call(app, api_key="invalid_key", ip=self.test_ip, status=400)
        self.check_response(data_queues, res, "invalid_key")
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:none"]
        )
        assert redis.keys("apiuser:*") == []

    def test_unknown_api_key(self, app, data_queues, redis, metricsmock):
        """A unknown API key is an error, and increments an "invalid" metric."""
        res = self._call(app, api_key="abcdefg", ip=self.test_ip, status=400)
        self.check_response(data_queues, res, "invalid_key")
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:invalid"]
        )
        assert redis.keys("apiuser:*") == []

    def test_gzip(self, app, data_queues):
        """A gzip-encoded body is uncompressed first."""
        wifis = WifiShardFactory.build_batch(2)
        query = self.model_query(wifis=wifis)

        body = util.encode_gzip(json.dumps(query).encode())
        headers = {"Content-Encoding": "gzip"}
        res = self._call(
            app, body=body, headers=headers, method="post", status=self.not_found.code
        )
        self.check_response(data_queues, res, "not_found")

    def test_truncated_gzip(self, app, data_queues):
        """An incomplete gzip-encoded body is an error."""
        wifis = WifiShardFactory.build_batch(2)
        query = self.model_query(wifis=wifis)

        body = util.encode_gzip(json.dumps(query).encode())[:-2]
        headers = {"Content-Encoding": "gzip"}
        res = self._call(app, body=body, headers=headers, method="post", status=400)
        detail = (
            "GZIPDecodeError(\"EOFError('Compressed file ended before the"
            " end-of-stream marker was reached')\")"
        )
        self.check_response(data_queues, res, "parse_error", details={"decode": detail})

    def test_bad_encoding(self, app, data_queues):
        """A badly encoded body is an error."""
        body = b'{"comment": "R\xe9sum\xe9 from 1990", "items": []}'
        assert "Résumé" in body.decode("iso8859-1")
        with pytest.raises(UnicodeDecodeError):
            body.decode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        res = self._call(app, body=body, headers=headers, method="post", status=400)
        detail = (
            "'utf-8' codec can't decode byte 0xe9 in position 14: invalid"
            " continuation byte"
        )
        self.check_response(data_queues, res, "parse_error", details={"decode": detail})


class CommonPositionTest(BaseLocateTest):
    """Tests for the locate_v1 API.

    TODO: These test are split out to support multiple location APIs, but the
    deprecated APIs were removed in 2019. This could be moved to test_locate_v1.py
    """

    def test_api_key_limit(self, app, data_queues, redis, session):
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

    def test_api_key_blocked(self, app, data_queues, session):
        """A 400 is returned when a key is blocked from locate APIs."""
        api_key = ApiKeyFactory(allow_locate=False, allow_region=False)
        session.flush()

        res = self._call(app, api_key=api_key.valid_key, ip=self.test_ip, status=400)
        self.check_response(data_queues, res, "invalid_key")

    def test_blue_not_found(self, app, data_queues, metricsmock):
        """A failed Bluetooth-based lookup emits several metrics."""
        blues = BlueShardFactory.build_batch(2)

        query = self.model_query(blues=blues)

        res = self._call(app, body=query, status=self.not_found.code)
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request",
            tags=[self.metric_path, "method:post", "status:%s" % self.not_found.code],
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
        metricsmock.assert_timing_once(
            "request.timing", tags=[self.metric_path, "method:post"]
        )

    def test_cell_not_found(self, app, data_queues, metricsmock):
        """A failed cell-based lookup emits several metrics."""
        cell = CellShardFactory.build()

        query = self.model_query(cells=[cell])
        res = self._call(app, body=query, status=self.not_found.code)
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request",
            tags=[self.metric_path, "method:post", "status:%s" % self.not_found.code],
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
        metricsmock.assert_timing_once(
            "request.timing", tags=[self.metric_path, "method:post"]
        )

    def test_cell_invalid_lac(self, app, data_queues):
        """A valid CID with and invalid LAC is not an error."""
        cell = CellShardFactory.build(radio=Radio.wcdma, lac=0, cid=1)
        query = self.model_query(cells=[cell])
        res = self._call(app, body=query, status=self.not_found.code)
        self.check_response(data_queues, res, "not_found")

    def test_cell_lte_radio(self, app, session, metricsmock):
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

    @pytest.mark.parametrize("fallback", ("explicit", "default", "ipf"))
    def test_cellarea(self, app, session, metricsmock, fallback):
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

    def test_cellarea_without_lacf(self, app, data_queues, session, metricsmock):
        """The cell location area fallback can be disabled."""
        cell = CellAreaFactory()
        session.flush()

        query = self.model_query(cells=[cell])
        query["fallbacks"] = {"lacf": False}

        res = self._call(app, body=query, status=self.not_found.code)
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request",
            tags=[self.metric_path, "method:post", "status:%s" % self.not_found.code],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )

    def test_wifi_not_found(self, app, data_queues, metricsmock):
        """A failed WiFi-based lookup emits several metrics."""
        wifis = WifiShardFactory.build_batch(2)

        query = self.model_query(wifis=wifis)

        res = self._call(app, body=query, status=self.not_found.code)
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request",
            tags=[self.metric_path, "method:post", "status:%s" % self.not_found.code],
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
        metricsmock.assert_timing_once(
            "request.timing", tags=[self.metric_path, "method:post"]
        )

    def test_ip_fallback_disabled(self, app, data_queues, metricsmock):
        """The IP-based location fallback can be disabled."""
        res = self._call(
            app,
            body={"fallbacks": {"ipf": 0}},
            ip=self.test_ip,
            status=self.not_found.code,
        )
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request",
            tags=[self.metric_path, "method:post", "status:%s" % self.not_found.code],
        )
        metricsmock.assert_incr_once(
            self.metric_type + ".request", tags=[self.metric_path, "key:test"]
        )
        metricsmock.assert_timing_once(
            "request.timing", tags=[self.metric_path, "method:post"]
        )

    @pytest.mark.parametrize("with_ip", [True, False])
    def test_fallback(self, app, session, metricsmock, with_ip):
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
        metricsmock.assert_timing_once(
            "request.timing", tags=[self.metric_path, "method:post"]
        )

    def test_store_sample_disabled(self, app, data_queues, session):
        """No requests are processed when store_sample_locate=0."""
        api_key = ApiKeyFactory(store_sample_locate=0)
        cell = CellShardFactory()
        session.flush()

        query = self.model_query(cells=[cell])
        res = self._call(app, body=query, api_key=api_key.valid_key, status=200)
        self.check_model_response(res, cell)
        self.check_queue(data_queues, 0)
