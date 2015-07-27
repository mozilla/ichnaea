"""
Implementation of a fallback source using an external web service.
"""

import time

import colander
import requests
from redis import RedisError
import simplejson as json

from ichnaea.api.schema import (
    OptionalMappingSchema,
    OptionalNode,
    OptionalSequenceSchema,
)
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import PositionSource
from ichnaea.models.cell import RadioStringType
from ichnaea.rate_limit import rate_limit_exceeded


class OutboundCellSchema(OptionalMappingSchema):

    radio = OptionalNode(RadioStringType(), internal_name='radioType')
    mcc = OptionalNode(colander.Integer(), internal_name='mobileCountryCode')
    mnc = OptionalNode(colander.Integer(), internal_name='mobileNetworkCode')
    lac = OptionalNode(colander.Integer(), internal_name='locationAreaCode')
    cid = OptionalNode(colander.Integer(), internal_name='cellId')
    signal = OptionalNode(colander.Integer(), internal_name='signalStrength')
    ta = OptionalNode(colander.Integer(), internal_name='timingAdvance')


class OutboundCellsSchema(OptionalSequenceSchema):

    cell = OutboundCellSchema()


class OutboundWifiSchema(OptionalMappingSchema):

    key = OptionalNode(colander.String(), internal_name='macAddress')
    channel = OptionalNode(colander.Integer(), internal_name='channel')
    signal = OptionalNode(colander.Integer(), internal_name='signalStrength')
    snr = OptionalNode(colander.Integer(), internal_name='signalToNoiseRatio')


class OutboundWifisSchema(OptionalSequenceSchema):

    wifi = OutboundWifiSchema()


class OutboundFallbackSchema(OptionalMappingSchema):

    lacf = OptionalNode(colander.Boolean())


class OutboundSchema(OptionalMappingSchema):

    cell = OutboundCellsSchema(
        missing=colander.drop, internal_name='cellTowers')
    wifi = OutboundWifisSchema(
        missing=colander.drop, internal_name='wifiAccessPoints')
    fallbacks = OutboundFallbackSchema(missing=colander.drop)


class FallbackPositionSource(PositionSource):
    """
    A FallbackPositionSource implements a search using
    an external web service.
    """

    source = DataSource.fallback
    LOCATION_NOT_FOUND = 404  #: Magic constant to cache not found.

    def __init__(self, settings, *args, **kw):
        self.url = settings.get('url')
        self.ratelimit = int(settings.get('ratelimit', 0))
        self.rate_limit_expire = int(settings.get('ratelimit_expire', 0))
        self.cache_expire = int(settings.get('cache_expire', 0))
        super(FallbackPositionSource, self).__init__(settings, *args, **kw)

    def _stat_count(self, stat):
        self.stats_client.incr('locate.fallback.' + stat)

    def _stat_timed(self, stat):
        return self.stats_client.timed('locate.fallback.' + stat)

    def _get_ratelimit_key(self):
        return 'fallback_ratelimit:{time}'.format(time=int(time.time()))

    def _limit_reached(self):
        return self.ratelimit and rate_limit_exceeded(
            self.redis_client,
            self._get_ratelimit_key(),
            maxreq=self.ratelimit,
            expire=self.rate_limit_expire,
            on_error=True,
        )

    def _should_cache(self, query):
        return (self.cache_expire and
                len(query.cell) == 1 and
                len(query.wifi) == 0)

    def _get_cache_key(self, cell_query):
        return 'fallback_cache_cell:{radio}:{mcc}:{mnc}:{lac}:{cid}'.format(
            radio=cell_query.radio.name,
            mcc=cell_query.mcc,
            mnc=cell_query.mnc,
            lac=cell_query.lac,
            cid=cell_query.cid,
        )

    def _get_cached_result(self, query):
        if self._should_cache(query):
            cache_key = self._get_cache_key(query.cell[0])
            try:
                cached_cell = self.redis_client.get(cache_key)
                if cached_cell:
                    self._stat_count('cache.hit')
                    return json.loads(cached_cell)
                else:
                    self._stat_count('cache.miss')
            except RedisError:
                self.raven_client.captureException()
        else:
            self._stat_count('cache.bypassed')

    def _set_cached_result(self, query, result):
        if self._should_cache(query):
            cache_key = self._get_cache_key(query.cell[0])
            try:
                self.redis_client.set(
                    cache_key,
                    json.dumps(result),
                    ex=self.cache_expire,
                )
            except RedisError:
                self.raven_client.captureException()

    def _make_external_call(self, query):
        outbound = None
        try:
            internal_query = query.internal_query()
            outbound = OutboundSchema().deserialize(internal_query)
        except colander.Invalid:  # pragma: no cover
            self.raven_client.captureException()

        if not outbound:  # pragma: no cover
            return

        try:
            with self._stat_timed('lookup'):
                response = requests.post(
                    self.url,
                    headers={'User-Agent': 'ichnaea'},
                    json=outbound,
                    timeout=5.0,
                    verify=False,
                )

            self._stat_count('lookup_status.' + str(response.status_code))
            if response.status_code != 404:
                # don't log exceptions for normal not found responses
                response.raise_for_status()
            else:
                return self.LOCATION_NOT_FOUND

            return response.json()

        except (json.JSONDecodeError, requests.exceptions.RequestException):
            self.raven_client.captureException()

    def should_search(self, query, result):
        empty_result = not result.found()
        weak_result = (result.source is not None and
                       result.source >= DataSource.geoip)

        return (
            query.api_key.allow_fallback and
            (empty_result or weak_result) and
            (bool(query.cell) or bool(query.wifi))
        )

    def search(self, query):
        result = self.result_type()
        source_used = False

        if not self._limit_reached():
            cached_result = self._get_cached_result(query)
            result_data = (
                cached_result or
                self._make_external_call(query)
            )

            if result_data and result_data != self.LOCATION_NOT_FOUND:
                try:
                    result = self.result_type(
                        lat=result_data['location']['lat'],
                        lon=result_data['location']['lng'],
                        accuracy=result_data['accuracy'],
                    )
                    source_used = True
                except (KeyError, TypeError):
                    self.raven_client.captureException()

            if cached_result is None:
                self._set_cached_result(query, result_data)

        if source_used:
            query.emit_source_stats(self.source, result)

        return result
