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
    InternalSchemaNode,
    InternalMappingSchema,
    OptionalMappingSchema,
    OptionalNode,
    OptionalSequenceSchema,
)
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import PositionSource
from ichnaea.api.rate_limit import rate_limit_exceeded
from ichnaea import floatjson
from ichnaea.geocalc import aggregate_position
from ichnaea.models.cell import (
    encode_cellid,
    RadioStringType,
)
from ichnaea.models.wifi import (
    encode_mac,
)

LOCATION_NOT_FOUND = '404'  #: Magic constant to cache not found.


class ExternalResult(namedtuple('ExternalResult',
                                'lat lon accuracy fallback')):
    __slots__ = ()

    def not_found(self):
        for field in ('lat', 'lon', 'accuracy'):
            if getattr(self, field, None) is None:
                return True
        return False


class ResultSchema(InternalMappingSchema):

    @colander.instantiate()
    class location(InternalMappingSchema):  # NOQA

        lat = InternalSchemaNode(BoundedFloat())
        lng = InternalSchemaNode(BoundedFloat(), internal_name='lon')

    accuracy = InternalSchemaNode(colander.Integer())
    fallback = OptionalNode(colander.String(), missing=None)

    def deserialize(self, data):
        data = super(ResultSchema, self).deserialize(data)
        fallback = data.get('fallback', None)
        if fallback != 'lacf':
            fallback = None
        return {
            'accuracy': data['accuracy'],
            'fallback': fallback,
            'lat': data['location']['lat'],
            'lon': data['location']['lon'],
        }

RESULT_SCHEMA = ResultSchema()


class OutboundSchema(OptionalMappingSchema):

    @colander.instantiate(missing=colander.drop)
    class fallbacks(OptionalMappingSchema):  # NOQA

        lacf = OptionalNode(colander.Boolean())

    @colander.instantiate(missing=colander.drop,
                          internal_name='cellTowers')  # NOQA
    class cell(OptionalSequenceSchema):

        @colander.instantiate()
        class SequenceItem(OptionalMappingSchema):

            radio = OptionalNode(
                RadioStringType(), internal_name='radioType')
            mcc = OptionalNode(
                colander.Integer(), internal_name='mobileCountryCode')
            mnc = OptionalNode(
                colander.Integer(), internal_name='mobileNetworkCode')
            lac = OptionalNode(
                colander.Integer(), internal_name='locationAreaCode')
            cid = OptionalNode(
                colander.Integer(), internal_name='cellId')
            signal = OptionalNode(
                colander.Integer(), internal_name='signalStrength')
            ta = OptionalNode(
                colander.Integer(), internal_name='timingAdvance')

    @colander.instantiate(missing=colander.drop,
                          internal_name='wifiAccessPoints')  # NOQA
    class wifi(OptionalSequenceSchema):

        @colander.instantiate()
        class SequenceItem(OptionalMappingSchema):

            key = OptionalNode(
                colander.String(), internal_name='macAddress')
            channel = OptionalNode(
                colander.Integer(), internal_name='channel')
            signal = OptionalNode(
                colander.Integer(), internal_name='signalStrength')
            snr = OptionalNode(
                colander.Integer(), internal_name='signalToNoiseRatio')

OUTBOUND_SCHEMA = OutboundSchema()


class FallbackCache(object):
    """
    A FallbackCache abstracts away the Redis based query result
    caching portion of the fallback position source logic.
    """

    def __init__(self, raven_client, redis_client, stats_client,
                 cache_expire=0):
        self.raven_client = raven_client
        self.redis_client = redis_client
        self.stats_client = stats_client
        self.cache_expire = cache_expire
        self.cache_key_cell = redis_client.cache_keys['fallback_cell']
        self.cache_key_wifi = redis_client.cache_keys['fallback_wifi']

    def _stat_count(self, stat, tags):
        self.stats_client.incr('locate.fallback.' + stat, tags=tags)

    def _should_cache(self, query):
        """
        Returns True if the query should be cached, otherwise False.

        A cell-only query with a single cell will be cached.

        A wifi-only query with up to 20 wifi networks will be cached.
        The 20 networks limit protects the cache memory from being
        exhausted.

        Queries with multiple cells or mixed cell and wifi networks
        won't get cached.
        """
        return ((not query.wifi and len(query.cell) == 1) or
                (not query.cell and query.wifi and len(query.wifi) < 20))

    def _cache_keys(self, query):
        # Dependent on should_cache conditions.
        if query.cell:
            return self._cache_keys_cell(query.cell)
        return self._cache_keys_wifi(query.wifi)

    def _cache_keys_cell(self, cell_query):
        keys = []
        for cell in cell_query:
            keys.append(self.cache_key_cell + encode_cellid(
                cell.radio, cell.mcc, cell.mnc, cell.lac, cell.cid))
        return keys

    def _cache_keys_wifi(self, wifi_query):
        keys = []
        for wifi in wifi_query:
            keys.append(self.cache_key_wifi + encode_mac(wifi.key))
        return keys

    def get(self, query):
        """
        Get a cached result for the query.

        :param query: The query for which to look for a cached value.
        :type query: :class:`ichnaea.api.locate.query.Query`

        :returns: The cache result or None.
        :rtype: :class:`~ichnaea.api.locate.fallback.ExternalResult`
        """
        if not self._should_cache(query):
            self._stat_count('cache', tags=['status:bypassed'])
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
            self._stat_count('cache', tags=['status:failure'])
            return None

        if not clustered_results:
            self._stat_count('cache', tags=['status:miss'])
            return None

        if list(clustered_results.keys()) == [not_found_cluster]:
            # the only match was for not found results
            self._stat_count('cache', tags=['status:hit'])
            return clustered_results[not_found_cluster][0]

        if len(clustered_results) == 1:
            # all the cached values agree with each other
            self._stat_count('cache', tags=['status:hit'])
            results = list(clustered_results.values())[0]
            circles = numpy.array(
                [(res.lat, res.lon, res.accuracy) for res in results],
                dtype=numpy.float64)
            lat, lon, accuracy = aggregate_position(circles, 10.0)
            _, accuracies = numpy.hsplit(circles, [2])
            return ExternalResult(
                lat=lat,
                lon=lon,
                accuracy=float(numpy.nanmax(accuracies)),
                fallback=results[0].fallback,
            )

        # inconsistent results
        self._stat_count('cache', tags=['status:inconsistent'])
        return None

    def set(self, query, result):
        """
        Cache the given position for all networks present in the query.

        :param query: The query for which we got a result.
        :type query: :class:`ichnaea.api.locate.query.Query`

        :param result: The position result obtained for the query.
        :type result: :class:`~ichnaea.api.locate.fallback.ExternalResult`
        """
        if not self._should_cache(query):
            return

        cache_keys = self._cache_keys(query)
        if result.not_found():
            cache_value = LOCATION_NOT_FOUND
        else:
            cache_value = result._asdict()

        try:
            cache_value = floatjson.float_dumps(cache_value)
            cache_values = dict([(key, cache_value) for key in cache_keys])

            with self.redis_client.pipeline() as pipe:
                pipe.mset(cache_values)
                for cache_key in cache_keys:
                    pipe.expire(cache_key, self.cache_expire)
                pipe.execute()
        except (simplejson.JSONDecodeError, RedisError):
            self.raven_client.captureException()


class DisabledCache(object):
    """
    A DisabledCache implements a no-cache version of the
    :class:`~ichnaea.api.locate.fallback.FallbackCache`.
    """

    def get(self, query):
        return None

    def set(self, query, result):
        pass


class FallbackPositionSource(PositionSource):
    """
    A FallbackPositionSource implements a search using
    an external web service.
    """

    outbound_schema = OUTBOUND_SCHEMA
    result_schema = RESULT_SCHEMA
    source = DataSource.fallback

    def __init__(self, settings, *args, **kw):
        super(FallbackPositionSource, self).__init__(settings, *args, **kw)
        self.url = settings.get('url')
        self.ratelimit = int(settings.get('ratelimit', 0))
        self.ratelimit_expire = int(settings.get('ratelimit_expire', 0))
        self.ratelimit_interval = int(settings.get('ratelimit_interval', 1))
        cache_expire = int(settings.get('cache_expire', 0))
        if not cache_expire:
            self.cache = DisabledCache()
        else:
            self.cache = FallbackCache(
                self.raven_client,
                self.redis_client,
                self.stats_client,
                cache_expire=cache_expire,
            )

    def _stat_count(self, stat, tags):
        self.stats_client.incr('locate.fallback.' + stat, tags=tags)

    def _stat_timed(self, stat, tags):
        return self.stats_client.timed('locate.fallback.' + stat, tags=tags)

    def _ratelimit_key(self):
        now = int(time.time())
        return 'fallback_ratelimit:%s' % (now // self.ratelimit_interval)

    def _ratelimit_reached(self):
        return self.ratelimit and rate_limit_exceeded(
            self.redis_client,
            self._ratelimit_key(),
            maxreq=self.ratelimit,
            expire=self.ratelimit_expire,
            on_error=True,
        )

    def _make_external_call(self, query):
        outbound = None
        try:
            internal_query = query.internal_query()
            outbound = self.outbound_schema.deserialize(internal_query)
        except colander.Invalid:  # pragma: no cover
            self.raven_client.captureException()

        if not outbound:  # pragma: no cover
            return None

        try:
            with self._stat_timed('lookup', tags=None):
                response = query.http_session.post(
                    self.url,
                    headers={'User-Agent': 'ichnaea'},
                    json=outbound,
                    timeout=5.0,
                )

            self._stat_count(
                'lookup', tags=['status:' + str(response.status_code)])

            if response.status_code == 404:
                # don't log exceptions for normal not found responses
                return ExternalResult(None, None, None, None)
            else:
                # raise_for_status is a no-op for successful 200 responses
                # so this only raises for 5xx responses
                response.raise_for_status()

            validated = None
            try:
                validated = self.result_schema.deserialize(response.json())
            except colander.Invalid:  # pragma: no cover
                self.raven_client.captureException()

            if not validated:  # pragma: no cover
                return None

            return ExternalResult(**validated)

        except (simplejson.JSONDecodeError, RequestException):
            self.raven_client.captureException()

    def should_search(self, query, results):
        return (
            query.api_key.allow_fallback and
            (bool(query.cell) or bool(query.wifi)) and
            not results.satisfies(query)
        )

    def search(self, query):
        result_data = None
        cached_result = self.cache.get(query)
        if cached_result:
            # use our own cache, without checking the rate limit
            result_data = cached_result
        elif not self._ratelimit_reached():
            # only rate limit the external call
            result_data = self._make_external_call(query)
            if result_data is not None:
                # we got a new possibly not_found answer
                self.cache.set(query, result_data)

        if result_data is not None and not result_data.not_found():
            result = self.result_type(
                lat=result_data.lat,
                lon=result_data.lon,
                accuracy=result_data.accuracy,
                fallback=result_data.fallback,
            )
        else:
            result = self.result_type()

        query.emit_source_stats(self.source, result)
        return result
