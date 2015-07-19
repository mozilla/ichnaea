"""
Implementation of a fallback provider using an external web service.
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
from ichnaea.api.locate.location import Position
from ichnaea.api.locate.provider import Provider
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


class FallbackProvider(Provider):
    """
    A FallbackProvider implements a search using
    an external web service.
    """

    log_name = 'fallback'
    location_type = Position
    source = DataSource.Fallback
    LOCATION_NOT_FOUND = 404  #: Magic constant to cache not found.

    def __init__(self, settings, *args, **kw):
        self.url = settings.get('url')
        self.ratelimit = int(settings.get('ratelimit', 0))
        self.rate_limit_expire = int(settings.get('ratelimit_expire', 0))
        self.cache_expire = int(settings.get('cache_expire', 0))
        super(FallbackProvider, self).__init__(settings, *args, **kw)

    def should_locate(self, query, location):
        empty_location = not location.found()
        weak_location = (location.source is not None and
                         location.source >= DataSource.GeoIP)

        return (
            query.api_key.allow_fallback and
            (empty_location or weak_location) and
            (bool(query.cell) or bool(query.wifi))
        )

    def get_ratelimit_key(self):
        return 'fallback_ratelimit:{time}'.format(time=int(time.time()))

    def limit_reached(self):
        return self.ratelimit and rate_limit_exceeded(
            self.redis_client,
            self.get_ratelimit_key(),
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
                    query.stat_count('fallback.cache.hit')
                    return json.loads(cached_cell)
                else:
                    query.stat_count('fallback.cache.miss')
            except RedisError:
                self.raven_client.captureException()

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
            with query.stat_timer('fallback.lookup'):
                response = requests.post(
                    self.url,
                    headers={'User-Agent': 'ichnaea'},
                    json=outbound,
                    timeout=5.0,
                    verify=False,
                )
            query.stat_count('fallback.lookup_status.' +
                             str(response.status_code))
            if response.status_code != 404:
                # don't log exceptions for normal not found responses
                response.raise_for_status()
            else:
                return self.LOCATION_NOT_FOUND

            return response.json()

        except (json.JSONDecodeError, requests.exceptions.RequestException):
            self.raven_client.captureException()

    def locate(self, query):
        location = self.location_type(query_data=False)

        if not self.limit_reached():

            cached_location = self._get_cached_result(query)
            location_data = (
                cached_location or
                self._make_external_call(query)
            )

            if location_data and location_data != self.LOCATION_NOT_FOUND:
                try:
                    location = self.location_type(
                        lat=location_data['location']['lat'],
                        lon=location_data['location']['lng'],
                        accuracy=location_data['accuracy'],
                    )
                except (KeyError, TypeError):
                    self.raven_client.captureException()

            if cached_location is None:
                self._set_cached_result(query, location_data)

        return location
