"""
Implementation of a fallback provider using an external web service.
"""

import time

import requests
from redis import RedisError
import simplejson as json

from ichnaea.api.locate.constants import (
    DataSource,
    MIN_WIFIS_IN_QUERY,
)
from ichnaea.api.locate.location import Position
from ichnaea.api.locate.provider import Provider
from ichnaea.rate_limit import rate_limit_exceeded


class FallbackProvider(Provider):
    """
    A FallbackProvider implements a search using
    an external web service.
    """

    log_name = 'fallback'
    location_type = Position
    source = DataSource.Fallback
    LOCATION_NOT_FOUND = True

    def __init__(self, settings, *args, **kwargs):
        self.url = settings['url']
        self.ratelimit = int(settings.get('ratelimit', 0))
        self.rate_limit_expire = int(settings.get('ratelimit_expire', 0))
        self.cache_expire = int(settings.get('cache_expire', 0))
        super(FallbackProvider, self).__init__(
            settings=settings, *args, **kwargs)

    def _prepare_cell(self, cell):
        radio = cell.radio
        if radio is not None:
            radio_name = radio.name
            if radio_name == 'umts':  # pragma: no cover
                radio_name = 'wcdma'

        result = {}
        cell_map = {
            'mcc': 'mobileCountryCode',
            'mnc': 'mobileNetworkCode',
            'lac': 'locationAreaCode',
            'cid': 'cellId',
            'signal': 'signalStrength',
            'ta': 'timingAdvance',
        }
        if radio_name:
            result['radioType'] = radio_name
        for source, target in cell_map.items():
            source_value = getattr(cell, source, None)
            if source_value is not None:
                result[target] = source_value

        return result

    def _prepare_wifi(self, wifi):
        result = {}
        wifi_map = {
            'key': 'macAddress',
            'channel': 'channel',
            'signal': 'signalStrength',
            'snr': 'signalToNoiseRatio',
        }
        for source, target in wifi_map.items():
            source_value = getattr(wifi, source, None)
            if source_value is not None:
                result[target] = source_value

        return result

    def _prepare_outbound_query(self, query):
        cell_queries = []
        for cell in query.cell:
            cell_query = self._prepare_cell(cell)
            if cell_query:
                cell_queries.append(cell_query)

        wifi_queries = []
        for wifi in query.wifi:
            wifi_query = self._prepare_wifi(wifi)
            if wifi_query:
                wifi_queries.append(wifi_query)

        outbound_query = {}
        if cell_queries:
            outbound_query['cellTowers'] = cell_queries
        if wifi_queries:
            outbound_query['wifiAccessPoints'] = wifi_queries
        outbound_query['fallbacks'] = {
            # We only send the lacf fallback for now
            'lacf': query.fallback.lacf,
        }

        return outbound_query

    def should_locate(self, query, location):
        empty_location = not location.found()
        weak_location = (location.source is not None and
                         location.source >= DataSource.GeoIP)

        outbound_query = self._prepare_outbound_query(query)
        cell_found = outbound_query.get('cellTowers', [])
        wifi_found = (len(outbound_query.get(
            'wifiAccessPoints', [])) >= MIN_WIFIS_IN_QUERY)
        return (
            self.api_key.allow_fallback and
            (empty_location or weak_location) and
            (cell_found or wifi_found)
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
                    self.stat_count('fallback.cache.hit')
                    return json.loads(cached_cell)
                else:
                    self.stat_count('fallback.cache.miss')
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
        outbound_query = self._prepare_outbound_query(query)

        try:
            with self.stat_timer('fallback.lookup'):
                response = requests.post(
                    self.url,
                    headers={'User-Agent': 'ichnaea'},
                    json=outbound_query,
                    timeout=5.0,
                    verify=False,
                )
            self.stat_count('fallback.lookup_status.%s' % response.status_code)
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

            if location_data and location_data is not self.LOCATION_NOT_FOUND:
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
