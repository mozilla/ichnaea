import uuid

from ichnaea.models.api import ApiKey


class TestApiKey(object):
    def test_fields(self, session):
        key = uuid.uuid4().hex
        session.add(
            ApiKey(
                valid_key=key,
                maxreq=10,
                allow_fallback=True,
                allow_locate=True,
                allow_region=True,
                fallback_name="test_fallback",
                fallback_schema="ichnaea/v1",
                fallback_url="https://localhost:9/api?key=k",
                fallback_ratelimit=100,
                fallback_ratelimit_interval=60,
                fallback_cache_expire=86400,
            )
        )
        session.flush()

        result = session.query(ApiKey).get(key)
        assert result.valid_key == key
        assert result.maxreq == 10
        assert result.allow_fallback is True
        assert result.allow_locate is True
        assert result.allow_region is True
        assert result.fallback_name == "test_fallback"
        assert result.fallback_schema == "ichnaea/v1"
        assert result.fallback_url == "https://localhost:9/api?key=k"
        assert result.fallback_ratelimit == 100
        assert result.fallback_ratelimit_interval == 60
        assert result.fallback_cache_expire == 86400
