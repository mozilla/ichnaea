from datetime import timedelta

from ichnaea.api.locate.tests.base import BaseLocateTest, CommonLocateTest
from ichnaea.models import Radio
from ichnaea.tests.factories import BlueShardFactory, CellShardFactory, WifiShardFactory
from ichnaea import util


class RegionBase(BaseLocateTest):

    url = "/v1/country"
    apikey_metrics = False
    metric_path = "path:v1.country"
    metric_type = "region"

    @property
    def ip_response(self):
        return {"country_code": "GB", "country_name": "United Kingdom"}

    def check_model_response(self, response, model, region=None, fallback=None, **kw):
        expected_names = set(["country_code", "country_name"])

        expected = super(RegionBase, self).check_model_response(
            response,
            model,
            region=region,
            fallback=fallback,
            expected_names=expected_names,
            **kw,
        )

        data = response.json
        assert data["country_code"] == expected["region"]
        if fallback is not None:
            assert data["fallback"] == fallback


class TestView(RegionBase, CommonLocateTest):
    def test_geoip(self, app, data_queues, metricsmock, logs):
        """GeoIP can be used to determine the region."""
        res = self._call(app, ip=self.test_ip)
        self.check_response(data_queues, res, "ok")
        assert res.headers["Access-Control-Allow-Origin"] == "*"
        assert res.headers["Access-Control-Max-Age"] == "2592000"
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:200"]
        )
        expected_entry = {
            "accuracy": "low",
            "accuracy_min": "low",
            "api_key": "test",
            "api_path": "v1.country",
            "api_type": "region",
            "blue": 0,
            "blue_valid": 0,
            "cell": 0,
            "cell_valid": 0,
            "duration_s": logs.entry["duration_s"],
            "event": "POST /v1/country - 200",
            "fallback_allowed": False,
            "has_geoip": True,
            "has_ip": True,
            "http_method": "POST",
            "http_path": "/v1/country",
            "http_status": 200,
            "log_level": "info",
            "region": "GB",
            "result_status": "hit",
            "source_geoip_accuracy": "low",
            "source_geoip_accuracy_min": "low",
            "source_geoip_status": "hit",
            "wifi": 0,
            "wifi_valid": 0,
        }
        assert logs.entry == expected_entry

    def test_geoip_miss(self, app, data_queues, metricsmock, logs):
        """GeoIP fails on some IPs, such as localhost."""
        res = self._call(app, ip="127.0.0.1", status=404)
        self.check_response(data_queues, res, "not_found")
        metricsmock.assert_incr_once(
            "request", tags=[self.metric_path, "method:post", "status:404"]
        )
        assert logs.entry["source_geoip_accuracy"] is None
        assert logs.entry["source_geoip_status"] == "miss"

    def test_incomplete_request(self, app, data_queues):
        res = self._call(app, body={"wifiAccessPoints": []}, ip=self.test_ip)
        self.check_response(data_queues, res, "ok")

    def test_blue(self, app, data_queues, session):
        # Use manual mac to ensure we only use one shard.
        blue1 = BlueShardFactory(mac="000000123456", samples=10)
        blue2 = BlueShardFactory(mac="000000abcdef", samples=10)
        session.flush()

        query = self.model_query(blues=[blue1, blue2])
        res = self._call(app, body=query, ip="127.0.0.1")
        self.check_response(data_queues, res, blue1)

    def test_cell(self, app, session):
        # cell with unique mcc to region mapping
        cell = CellShardFactory(mcc=235)
        session.flush()

        query = self.model_query(cells=[cell])
        res = self._call(app, body=query)
        self.check_model_response(res, cell, region="GB")

    def test_cell_ambiguous(self, app, session):
        # cell with ambiguous mcc to region mapping
        cell = CellShardFactory(mcc=234)
        session.flush()

        query = self.model_query(cells=[cell])
        res = self._call(app, body=query)
        self.check_model_response(res, cell, region="GB")

    def test_cell_geoip_match(self, app, session):
        cell = CellShardFactory(mcc=234)
        session.flush()

        query = self.model_query(cells=[cell])
        res = self._call(app, body=query, ip=self.test_ip)
        self.check_model_response(res, cell, region="GB")

    def test_cell_geoip_mismatch(self, app, session):
        # UK GeoIP with ambiguous US mcc
        uk_cell = CellShardFactory.build(mcc=234)
        us_cell = CellShardFactory(mcc=310)
        session.flush()

        query = self.model_query(cells=[us_cell])
        res = self._call(app, body=query, ip=self.test_ip)
        self.check_model_response(res, uk_cell, region="GB", fallback="ipf")

    def test_cell_over_geoip(self, app, session):
        # UK GeoIP with single DE cell
        cell = CellShardFactory(mcc=262)
        session.flush()

        query = self.model_query(cells=[cell])
        res = self._call(app, body=query, ip=self.test_ip)
        self.check_model_response(res, cell, region="DE")

    def test_cells_over_geoip(self, app, session):
        # UK GeoIP with multiple US cells
        us_cell1 = CellShardFactory(radio=Radio.gsm, mcc=310, samples=100)
        us_cell2 = CellShardFactory(radio=Radio.lte, mcc=311, samples=100)
        session.flush()

        query = self.model_query(cells=[us_cell1, us_cell2])
        res = self._call(app, body=query, ip=self.test_ip)
        self.check_model_response(res, us_cell1, region="US")

    def test_wifi(self, app, data_queues, session):
        # Use manual mac to ensure we only use one shard.
        wifi1 = WifiShardFactory(mac="000000123456", samples=10)
        wifi2 = WifiShardFactory(mac="000000abcdef", samples=10)
        session.flush()

        query = self.model_query(wifis=[wifi1, wifi2])
        res = self._call(app, body=query, ip="127.0.0.1")
        self.check_response(data_queues, res, wifi1)

    def test_wifi_over_cell(self, app, session):
        now = util.utcnow()
        three_months = now - timedelta(days=90)
        wifi1 = WifiShardFactory(
            samples=1000, created=three_months, modified=now, region="US"
        )
        wifi2 = WifiShardFactory(
            samples=1000, created=three_months, modified=now, region="US"
        )
        cell = CellShardFactory(radio=Radio.gsm, samples=10)
        session.flush()

        query = self.model_query(cells=[cell], wifis=[wifi1, wifi2])
        res = self._call(app, body=query, ip=self.test_ip)
        # wifi says US with a high score, cell and geoip say UK
        self.check_model_response(res, wifi1, region="US")
