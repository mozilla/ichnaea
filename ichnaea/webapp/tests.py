import pytest
import webtest

from ichnaea.cache import configure_redis
from ichnaea.db import configure_db
from ichnaea.geoip import GeoIPNull
from ichnaea.webapp.config import main


def _make_app(
    _db=None,
    _http_session=None,
    _geoip_db=None,
    _raven_client=None,
    _redis_client=None,
    _position_searcher=None,
    _region_searcher=None,
):
    wsgiapp = main(
        _db=_db,
        _geoip_db=_geoip_db,
        _http_session=_http_session,
        _raven_client=_raven_client,
        _redis_client=_redis_client,
        _position_searcher=_position_searcher,
        _region_searcher=_region_searcher,
    )
    return webtest.TestApp(wsgiapp)


class TestApp(object):
    def test_compiles(self):
        from ichnaea.webapp import app

        assert hasattr(app, "wsgi_app")

    def test_db_hooks(self, app, db):
        # Check that our _db hooks are passed through.
        assert app.app.registry.db is db


class TestContribute(object):
    def test_ok(self, app):
        response = app.get("/contribute.json", status=200)
        assert response.content_type == "application/json"
        data = response.json
        assert "repository" in data.keys()
        assert "license" in data["repository"]
        assert data["repository"]["license"] == "Apache 2.0"


class TestHeartbeat(object):
    def test_ok(self, app):
        response = app.get("/__heartbeat__", status=200)
        assert response.content_type == "application/json"
        data = response.json
        timed_services = set(["database", "geoip", "redis"])
        assert set(data.keys()) == timed_services

        for name in timed_services:
            assert data[name]["up"]
            assert isinstance(data[name]["time"], int)
            assert data[name]["time"] >= 0

        # Run "make download" when this gets too old
        assert 1 < data["geoip"]["age_in_days"] < 1000


class TestHeartbeatErrors(object):
    @pytest.fixture(scope="function")
    def broken_app(self, http_session, raven):
        # Create database connections to the discard port.
        db = configure_db("rw", uri="mysql+pymysql://none:none@127.0.0.1:9/none")

        # Create a broken GeoIP database.
        geoip_db = GeoIPNull()

        # Create a broken Redis client.
        redis_client = configure_redis("redis://127.0.0.1:9/15")

        app = _make_app(
            _db=db,
            _geoip_db=geoip_db,
            _http_session=http_session,
            _raven_client=raven,
            _redis_client=redis_client,
        )
        yield app

        db.close()
        geoip_db.close()
        redis_client.close()

    def test_database(self, broken_app):
        res = broken_app.get("/__heartbeat__", status=503)
        assert res.content_type == "application/json"
        assert res.json["database"] == {
            "up": False,
            "time": 0,
            "alembic_version": "unknown",
        }
        assert res.headers["Access-Control-Allow-Origin"] == "*"
        assert res.headers["Access-Control-Max-Age"] == "2592000"

    def test_geoip(self, broken_app):
        res = broken_app.get("/__heartbeat__", status=503)
        assert res.content_type == "application/json"
        assert res.json["geoip"] == {"up": False, "time": 0, "age_in_days": -1}

    def test_redis(self, broken_app):
        res = broken_app.get("/__heartbeat__", status=503)
        assert res.content_type == "application/json"
        assert res.json["redis"] == {"up": False, "time": 0}

    def test_lbheartbeat(self, broken_app):
        res = broken_app.get("/__lbheartbeat__", status=200)
        assert res.content_type == "application/json"
        assert res.json["status"] == "OK"


class TestLBHeartbeat(object):
    def test_get(self, app):
        res = app.get("/__lbheartbeat__", status=200)
        assert res.content_type == "application/json"
        assert res.json["status"] == "OK"
        assert res.headers["Access-Control-Allow-Origin"] == "*"
        assert res.headers["Access-Control-Max-Age"] == "2592000"

    def test_head(self, app):
        res = app.head("/__lbheartbeat__", status=200)
        assert res.content_type == "application/json"
        assert res.body == b""

    def test_post(self, app):
        res = app.post("/__lbheartbeat__", status=200)
        assert res.content_type == "application/json"
        assert res.json["status"] == "OK"

    def test_options(self, app):
        res = app.options(
            "/__lbheartbeat__",
            status=200,
            headers={
                "Access-Control-Request-Method": "POST",
                "Origin": "localhost.local",
            },
        )
        assert res.headers["Access-Control-Allow-Origin"] == "*"
        assert res.headers["Access-Control-Max-Age"] == "2592000"
        assert res.content_length is None
        assert res.content_type is None

    def test_unsupported_methods(self, app):
        app.delete("/__lbheartbeat__", status=405)
        app.patch("/__lbheartbeat__", status=405)
        app.put("/__lbheartbeat__", status=405)


class TestGunicornSettings(object):
    def test_gunicorn_settings_loads(self):
        # import this to make sure it is importable
        from ichnaea.webapp import gunicorn_settings  # noqa


class TestVersion(object):
    def test_ok(self, app):
        response = app.get("/__version__", status=200)
        assert response.content_type == "application/json"
        data = response.json
        assert set(data.keys()) == set(["build", "commit", "source", "version"])
        assert data["source"] == "https://github.com/mozilla/ichnaea"


class TestWorker(object):
    def test_compiles(self):
        from ichnaea.webapp import worker

        assert hasattr(worker, "LocationGeventWorker")
