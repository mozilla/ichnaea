"""
Implementation of a fallback source using an external web service.
"""

from collections import defaultdict, namedtuple
import time

import colander
import numpy
from requests.exceptions import RequestException
from redis import RedisError
import simplejson

from ichnaea.api.schema import (
    BoundedFloat,
    OptionalMappingSchema,
    OptionalNode,
    OptionalSequenceSchema,
    RenamingMappingSchema,
)
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import PositionSource
from ichnaea.api.rate_limit import rate_limit_exceeded
from geocalc import distance

# Magic constant to cache not found.
LOCATION_NOT_FOUND = '404'

# Supported fallback schemata
COMBAIN_V1_SCHEMA = 'combain/v1'
ICHNAEA_V1_SCHEMA = 'ichnaea/v1'
GOOGLEMAPS_V1_SCHEMA = 'googlemaps/v1'
UNWIREDLABS_V1_SCHEMA = 'unwiredlabs/v1'
# Default fallback schema, if schema is None/NULL
DEFAULT_SCHEMA = ICHNAEA_V1_SCHEMA


class ExternalResult(namedtuple('ExternalResult',
                                'lat lon accuracy fallback')):
    __slots__ = ()

    def not_found(self):
        for field in ('lat', 'lon', 'accuracy'):
            if getattr(self, field, None) is None:
                return True
        return False

    @property
    def score(self):
        if self.fallback:
            return 5.0
        return 10.0


class IchnaeaV1ResultSchema(RenamingMappingSchema):

    @colander.instantiate()
    class location(RenamingMappingSchema):  # NOQA

        lat = colander.SchemaNode(BoundedFloat())
        lng = colander.SchemaNode(BoundedFloat(), to_name='lon')

    accuracy = colander.SchemaNode(colander.Float())
    fallback = OptionalNode(colander.String(), missing=None)

    def deserialize(self, data):
        data = super(IchnaeaV1ResultSchema, self).deserialize(data)
        fallback = data.get('fallback', None)
        if fallback != 'lacf':
            fallback = None
        return {
            'accuracy': data['accuracy'],
            'fallback': fallback,
            'lat': data['location']['lat'],
            'lon': data['location']['lon'],
        }


ICHNAEA_V1_RESULT_SCHEMA = IchnaeaV1ResultSchema()


class IchnaeaV1OutboundSchema(OptionalMappingSchema):

    @colander.instantiate()
    class fallbacks(RenamingMappingSchema):  # NOQA

        lacf = colander.SchemaNode(colander.Boolean(), missing=True)

    @colander.instantiate(missing=colander.drop)
    class bluetoothBeacons(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(OptionalMappingSchema):

            macAddress = OptionalNode(colander.String())
            age = OptionalNode(colander.Integer())
            name = OptionalNode(colander.String())
            signalStrength = OptionalNode(colander.Integer())

    @colander.instantiate(missing=colander.drop)
    class cellTowers(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(OptionalMappingSchema):

            radioType = OptionalNode(colander.String())
            mobileCountryCode = OptionalNode(colander.Integer())
            mobileNetworkCode = OptionalNode(colander.Integer())
            locationAreaCode = OptionalNode(colander.Integer())
            cellId = OptionalNode(colander.Integer())
            primaryScramblingCode = OptionalNode(colander.Integer())
            age = OptionalNode(colander.Integer())
            signalStrength = OptionalNode(colander.Integer())
            timingAdvance = OptionalNode(colander.Integer())

    @colander.instantiate(missing=colander.drop)
    class wifiAccessPoints(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(OptionalMappingSchema):

            macAddress = OptionalNode(colander.String())
            age = OptionalNode(colander.Integer())
            channel = OptionalNode(colander.Integer())
            signalStrength = OptionalNode(colander.Integer())
            signalToNoiseRatio = OptionalNode(colander.Integer())
            ssid = OptionalNode(colander.String())


ICHNAEA_V1_OUTBOUND_SCHEMA = IchnaeaV1OutboundSchema()


class GoogleMapsV1OutboundSchema(OptionalMappingSchema):

    considerIp = colander.SchemaNode(colander.Boolean(), missing=False)

    @colander.instantiate(missing=colander.drop)
    class cellTowers(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(OptionalMappingSchema):

            radioType = OptionalNode(colander.String())
            mobileCountryCode = OptionalNode(colander.Integer())
            mobileNetworkCode = OptionalNode(colander.Integer())
            locationAreaCode = OptionalNode(colander.Integer())
            cellId = OptionalNode(colander.Integer())
            age = OptionalNode(colander.Integer())
            signalStrength = OptionalNode(colander.Integer())
            timingAdvance = OptionalNode(colander.Integer())

    @colander.instantiate(missing=colander.drop)
    class wifiAccessPoints(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(OptionalMappingSchema):

            macAddress = OptionalNode(colander.String())
            age = OptionalNode(colander.Integer())
            channel = OptionalNode(colander.Integer())
            signalStrength = OptionalNode(colander.Integer())
            signalToNoiseRatio = OptionalNode(colander.Integer())


GOOGLEMAPS_V1_OUTBOUND_SCHEMA = GoogleMapsV1OutboundSchema()


class UnwiredlabsV1ResultSchema(RenamingMappingSchema):

    status = colander.SchemaNode(colander.String())
    message = colander.SchemaNode(colander.String(), missing=None)
    lat = colander.SchemaNode(BoundedFloat(), missing=None)
    lon = colander.SchemaNode(BoundedFloat(), missing=None)
    accuracy = colander.SchemaNode(colander.Float(), missing=None)
    fallback = OptionalNode(colander.String(), missing=None)

    def deserialize(self, data):
        data = super(UnwiredlabsV1ResultSchema, self).deserialize(data)

        # The API always returns 200 Ok responses, but uses the
        # status/message fields to indicate failures.
        status = data.get('status', None)
        if status != 'ok':
            message = data.get('message', None)
            if message == 'No matches found':
                # Fabricate a not found
                return {
                    'accuracy': None,
                    'fallback': None,
                    'lat': None,
                    'lon': None,
                }

            raise colander.Invalid('Error response, message: %s' % message)

        # Check required fields for status==ok responses
        for field in ('lat', 'lon', 'accuracy'):
            if data.get(field, None) is None:
                raise colander.Invalid('Missing required field: %s' % field)

        fallback = data.get('fallback', None)
        if fallback != 'lacf':
            fallback = None

        return {
            'accuracy': data['accuracy'],
            'fallback': fallback,
            'lat': data['lat'],
            'lon': data['lon'],
        }


UNWIREDLABS_V1_RESULT_SCHEMA = UnwiredlabsV1ResultSchema()


class UnwiredlabsV1OutboundSchema(RenamingMappingSchema):

    token = colander.SchemaNode(colander.String(), missing=None)

    @colander.instantiate()
    class fallbacks(RenamingMappingSchema):  # NOQA

        lacf = colander.SchemaNode(colander.Boolean(), missing=True)

    @colander.instantiate(missing=colander.drop, to_name='cells')
    class cellTowers(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(OptionalMappingSchema):

            radioType = OptionalNode(colander.String(), to_name='radio')
            locationAreaCode = OptionalNode(colander.Integer(), to_name='lac')
            cellId = OptionalNode(colander.Integer(), to_name='cid')
            mobileCountryCode = OptionalNode(colander.Integer(), to_name='mcc')
            mobileNetworkCode = OptionalNode(colander.Integer(), to_name='mnc')
            signalStrength = OptionalNode(colander.Integer(), to_name='signal')
            timingAdvance = OptionalNode(colander.Integer(), to_name='tA')
            primaryScramblingCode = OptionalNode(
                colander.Integer(), to_name='psc')
            asu = OptionalNode(colander.Integer())

    @colander.instantiate(missing=colander.drop, to_name='wifi')
    class wifiAccessPoints(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(OptionalMappingSchema):

            macAddress = OptionalNode(colander.String(), to_name='bssid')
            channel = OptionalNode(colander.Integer())
            frequency = OptionalNode(colander.Integer())
            signalStrength = OptionalNode(colander.Integer(), to_name='signal')
            signalToNoiseRatio = OptionalNode(colander.Integer())


UNWIREDLABS_V1_OUTBOUND_SCHEMA = UnwiredlabsV1OutboundSchema()


class FallbackCache(object):
    """
    A FallbackCache abstracts away the Redis based query result
    caching portion of the fallback position source logic.
    """

    # Define Redis keys for the fallback cache. Include the schema
    # name and an integer version. Increase the integer if the way
    # we cache contents changes.
    cache_keys = {
        COMBAIN_V1_SCHEMA: {
            'fallback_blue': b'cache:fallback:combain:v1:1:blue:',
            'fallback_cell': b'cache:fallback:combain:v1:1:cell:',
            'fallback_wifi': b'cache:fallback:combain:v1:1:wifi:',
        },
        GOOGLEMAPS_V1_SCHEMA: {
            'fallback_blue': b'cache:fallback:googlemaps:v1:1:blue:',
            'fallback_cell': b'cache:fallback:googlemaps:v1:1:cell:',
            'fallback_wifi': b'cache:fallback:googlemaps:v1:1:wifi:',
        },
        ICHNAEA_V1_SCHEMA: {
            'fallback_blue': b'cache:fallback:ichnaea:v1:1:blue:',
            'fallback_cell': b'cache:fallback:ichnaea:v1:1:cell:',
            'fallback_wifi': b'cache:fallback:ichnaea:v1:1:wifi:',
        },
        UNWIREDLABS_V1_SCHEMA: {
            'fallback_blue': b'cache:fallback:unwiredlabs:v1:1:blue:',
            'fallback_cell': b'cache:fallback:unwiredlabs:v1:1:cell:',
            'fallback_wifi': b'cache:fallback:unwiredlabs:v1:1:wifi:',
        }
    }

    def __init__(self, raven_client, redis_client, stats_client,
                 schema=DEFAULT_SCHEMA):
        self.raven_client = raven_client
        self.redis_client = redis_client
        self.stats_client = stats_client
        self.schema = DEFAULT_SCHEMA
        self.cache_key_blue = self.cache_keys[schema]['fallback_blue']
        self.cache_key_cell = self.cache_keys[schema]['fallback_cell']
        self.cache_key_wifi = self.cache_keys[schema]['fallback_wifi']

    def _stat_count(self, fallback_name, status):
        tags = ['fallback_name:%s' % fallback_name,
                'status:%s' % status]
        self.stats_client.incr('locate.fallback.cache', tags=tags)

    def _should_cache(self, query):
        """
        Returns True if the query should be cached, otherwise False.

        A blue-only query with up to 20 Bluetooth networks will be cached.

        A cell-only query with a single cell will be cached.

        A wifi-only query with up to 20 WiFi networks will be cached.

        The 20 networks limit protects the cache memory from being
        exhausted.

        Queries with multiple cells or mixed blue, cell and wifi networks
        won't get cached.
        """
        return (query.api_key.fallback_cache_expire and
                ((not query.blue and not query.wifi and
                  len(query.cell) == 1) or
                 (not query.blue and not query.cell and
                  query.wifi and len(query.wifi) < 20) or
                 (not query.cell and not query.wifi and
                  query.blue and len(query.blue) < 20)))

    def _cache_keys(self, query):
        # Dependent on should_cache conditions.
        if query.blue:
            return self._cache_keys_blue(query.blue)
        if query.cell:
            return self._cache_keys_cell(query.cell)
        return self._cache_keys_wifi(query.wifi)

    def _cache_keys_blue(self, blue_query):
        keys = []
        for blue in blue_query:
            keys.append(self.cache_key_blue + blue.mac)
        return keys

    def _cache_keys_cell(self, cell_query):
        keys = []
        for cell in cell_query:
            keys.append(self.cache_key_cell + cell.cellid)
        return keys

    def _cache_keys_wifi(self, wifi_query):
        keys = []
        for wifi in wifi_query:
            keys.append(self.cache_key_wifi + wifi.mac)
        return keys

    def get(self, query):
        """
        Get a cached result for the query.

        :param query: The query for which to look for a cached value.
        :type query: :class:`ichnaea.api.locate.query.Query`

        :returns: The cache result or None.
        :rtype: :class:`~ichnaea.api.locate.fallback.ExternalResult`
        """
        fallback_name = query.api_key.fallback_name

        if not self._should_cache(query):
            self._stat_count(fallback_name, 'bypassed')
            return None

        cache_keys = self._cache_keys(query)
        # dict of (lat, lon, fallback) tuples to ExternalResult list
        # lat/lon clustered into ~100x100 meter grid cells
        clustered_results = defaultdict(list)
        not_found_cluster = (None, None, None)
        try:
            for value in self.redis_client.mget(cache_keys):
                if not value:
                    continue

                value = simplejson.loads(value)
                if value == LOCATION_NOT_FOUND:
                    value = ExternalResult(None, None, None, None)
                    clustered_results[not_found_cluster] = [value]
                else:
                    value = ExternalResult(**value)
                    # ~100x100m clusters
                    clustered_results[(round(value.lat, 3),
                                       round(value.lat, 3),
                                       value.fallback)].append(value)
        except (simplejson.JSONDecodeError, RedisError):
            self.raven_client.captureException()
            self._stat_count(fallback_name, 'failure')
            return None

        if not clustered_results:
            self._stat_count(fallback_name, 'miss')
            return None

        if list(clustered_results.keys()) == [not_found_cluster]:
            # the only match was for not found results
            self._stat_count(fallback_name, 'hit')
            return clustered_results[not_found_cluster][0]

        if len(clustered_results) == 1:
            # all the cached values agree with each other
            self._stat_count(fallback_name, 'hit')
            results = list(clustered_results.values())[0]

            circles = numpy.array(
                [(res.lat, res.lon, res.accuracy) for res in results],
                dtype=numpy.double)
            points, accuracies = numpy.hsplit(circles, [2])

            lat, lon = points.mean(axis=0)
            lat = float(lat)
            lon = float(lon)

            radius = 0.0
            for circle in circles:
                p_dist = distance(lat, lon, circle[0], circle[1]) + circle[2]
                radius = max(radius, p_dist)

            return ExternalResult(
                lat=lat,
                lon=lon,
                accuracy=float(radius),
                fallback=results[0].fallback,
            )

        # inconsistent results
        self._stat_count(fallback_name, 'inconsistent')
        return None

    def set(self, query, result, expire=3600):
        """
        Cache the given position for all networks present in the query.

        :param query: The query for which we got a result.
        :type query: :class:`ichnaea.api.locate.query.Query`

        :param result: The position result obtained for the query.
        :type result: :class:`~ichnaea.api.locate.fallback.ExternalResult`

        :param expire: Time in seconds to cache the result.
        :type expire: int
        """
        if not self._should_cache(query):
            return

        cache_keys = self._cache_keys(query)
        if result.not_found():
            cache_value = LOCATION_NOT_FOUND
        else:
            cache_value = result._asdict()

        try:
            cache_value = simplejson.dumps(cache_value)
            cache_values = dict([(key, cache_value) for key in cache_keys])

            with self.redis_client.pipeline() as pipe:
                pipe.mset(cache_values)
                for cache_key in cache_keys:
                    pipe.expire(cache_key, expire)
                pipe.execute()
        except (simplejson.JSONDecodeError, RedisError):
            self.raven_client.captureException()


def _add_fallback_ipf_false(payload):
    # Disable ipf fallback, so we don't get position estimates
    # based on the IP address of the service.

    # Make shallow copies of payload parts, to avoid mutating argument,
    # but avoid full deepcopy of the potentially large network parts.
    new_payload = payload.copy()
    new_fallbacks = new_payload['fallbacks'].copy()
    new_fallbacks['ipf'] = False
    new_payload['fallbacks'] = new_fallbacks
    return new_payload


def _external_call_ichnaea_v1(query, payload):
    new_payload = _add_fallback_ipf_false(payload)
    return query.http_session.post(
        query.api_key.fallback_url,
        headers={'User-Agent': 'ichnaea'},
        json=new_payload,
        timeout=5.0,
    )


def _external_call_combain_v1(query, payload):
    new_payload = _add_fallback_ipf_false(payload)
    return query.http_session.post(
        query.api_key.fallback_url,
        headers={'User-Agent': 'ichnaea'},
        json=new_payload,
        timeout=5.0,
    )


def _external_call_googlemaps_v1(query, payload):
    # There is no fallbacks section, the schema takes care of adding
    # a new top-level considerIp: false
    return query.http_session.post(
        query.api_key.fallback_url,
        headers={'User-Agent': 'ichnaea'},
        json=payload,
        timeout=5.0,
    )


def _external_call_unwiredlabs_v1(query, payload):
    new_payload = _add_fallback_ipf_false(payload)

    # Parse the token from the URL and put it into the body.
    url, token = query.api_key.fallback_url.split('#')
    new_payload['token'] = token

    return query.http_session.post(
        url,
        headers={'User-Agent': 'ichnaea'},
        json=new_payload,
        timeout=5.0,
    )


class FallbackPositionSource(PositionSource):
    """
    A FallbackPositionSource implements a search using
    an external web service.
    """

    source = DataSource.fallback

    # The schema for ichnaea, combain and googlemaps are currently
    # almost the same.
    schemas = (
        COMBAIN_V1_SCHEMA,
        GOOGLEMAPS_V1_SCHEMA,
        ICHNAEA_V1_SCHEMA,
        UNWIREDLABS_V1_SCHEMA,
    )
    outbound_schemas = {
        COMBAIN_V1_SCHEMA: ICHNAEA_V1_OUTBOUND_SCHEMA,
        GOOGLEMAPS_V1_SCHEMA: GOOGLEMAPS_V1_OUTBOUND_SCHEMA,
        ICHNAEA_V1_SCHEMA: ICHNAEA_V1_OUTBOUND_SCHEMA,
        UNWIREDLABS_V1_SCHEMA: UNWIREDLABS_V1_OUTBOUND_SCHEMA,
    }
    outbound_calls = {
        COMBAIN_V1_SCHEMA: _external_call_combain_v1,
        GOOGLEMAPS_V1_SCHEMA: _external_call_googlemaps_v1,
        ICHNAEA_V1_SCHEMA: _external_call_ichnaea_v1,
        UNWIREDLABS_V1_SCHEMA: _external_call_unwiredlabs_v1,
    }
    result_schemas = {
        COMBAIN_V1_SCHEMA: ICHNAEA_V1_RESULT_SCHEMA,
        GOOGLEMAPS_V1_SCHEMA: ICHNAEA_V1_RESULT_SCHEMA,
        ICHNAEA_V1_SCHEMA: ICHNAEA_V1_RESULT_SCHEMA,
        UNWIREDLABS_V1_SCHEMA: UNWIREDLABS_V1_RESULT_SCHEMA,
    }

    def __init__(self, *args, **kw):
        super(FallbackPositionSource, self).__init__(*args, **kw)
        # Initialze one cache per possible schema.
        self.caches = {}
        for schema in self.schemas:
            self.caches[schema] = FallbackCache(
                self.raven_client,
                self.redis_client,
                self.stats_client,
                schema=schema,
            )

    def _stat_count(self, stat, tags):
        self.stats_client.incr('locate.fallback.' + stat, tags=tags)

    def _stat_timed(self, stat, tags):
        return self.stats_client.timed('locate.fallback.' + stat, tags=tags)

    def _ratelimit_key(self, name, interval):
        now = int(time.time())
        return 'fallback_ratelimit:%s:%s' % (name, now // interval)

    def _ratelimit_reached(self, query):
        api_key = query.api_key
        name = api_key.fallback_name or ''
        limit = api_key.fallback_ratelimit or 0
        interval = api_key.fallback_ratelimit_interval or 1
        ratelimit_key = self._ratelimit_key(name, interval)

        return limit and rate_limit_exceeded(
            self.redis_client,
            ratelimit_key,
            maxreq=limit,
            expire=interval * 5,
            on_error=True,
        )

    def _make_external_call(self, query, fallback_schema):
        outbound = None
        outbound_schema = self.outbound_schemas[fallback_schema]
        outbound_call = self.outbound_calls[fallback_schema]
        result_schema = self.result_schemas[fallback_schema]

        try:
            outbound = outbound_schema.deserialize(query.json())
        except colander.Invalid:  # pragma: no cover
            self.raven_client.captureException()

        if not outbound:  # pragma: no cover
            return None

        try:
            fallback_tag = 'fallback_name:%s' % (
                query.api_key.fallback_name or 'none')

            with self._stat_timed('lookup', tags=[fallback_tag]):
                response = outbound_call(query, outbound)

            self._stat_count(
                'lookup', tags=[fallback_tag,
                                'status:' + str(response.status_code)])

            if response.status_code == 404:
                # don't log exceptions for normal not found responses
                return ExternalResult(None, None, None, None)
            else:
                # raise_for_status is a no-op for successful 200 responses
                # so this only raises for 5xx responses
                response.raise_for_status()

            validated = None
            try:
                body = response.json()
                validated = result_schema.deserialize(body)
            except (colander.Invalid,
                    simplejson.JSONDecodeError):  # pragma: no cover
                self.raven_client.captureException()

            if not validated:  # pragma: no cover
                return None

            return ExternalResult(**validated)

        except (simplejson.JSONDecodeError, RequestException):
            self.raven_client.captureException()

    def should_search(self, query, results):
        return (
            query.api_key.can_fallback() and
            (bool(query.blue) or bool(query.cell) or bool(query.wifi)) and
            not results.satisfies(query)
        )

    def search(self, query):
        # Determine fallback schema, default to our own
        fallback_schema = query.api_key.fallback_schema
        if fallback_schema is None:
            fallback_schema = DEFAULT_SCHEMA

        cache = self.caches[fallback_schema]
        results = self.result_list()
        result_data = None

        cached_result = cache.get(query)
        if cached_result:
            # use our own cache, without checking the rate limit
            result_data = cached_result
        elif not self._ratelimit_reached(query):
            # only rate limit the external call
            result_data = self._make_external_call(query, fallback_schema)
            if result_data is not None:
                # we got a new possibly not_found answer
                cache.set(query, result_data,
                          expire=query.api_key.fallback_cache_expire or 1)

        if result_data is not None and not result_data.not_found():
            results.add(self.result_type(
                lat=result_data.lat,
                lon=result_data.lon,
                accuracy=result_data.accuracy,
                score=result_data.score,
                fallback=result_data.fallback,
            ))

        query.emit_source_stats(self.source, results)
        return results
