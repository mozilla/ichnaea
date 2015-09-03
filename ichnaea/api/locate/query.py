"""Code representing a query."""

import six

from ichnaea.api.locate.constants import (
    DataAccuracy,
    MIN_WIFIS_IN_QUERY,
)
from ichnaea.api.locate.schema import (
    CellAreaLookup,
    CellLookup,
    FallbackLookup,
    WifiLookup,
)

try:
    from collections import OrderedDict
except ImportError:  # pragma: no cover
    from ordereddict import OrderedDict

if six.PY2:  # pragma: no cover
    from ipaddr import IPAddress as ip_address  # NOQA
else:  # pragma: no cover
    from ipaddress import ip_address

METRIC_MAPPING = {
    0: 'none',
    1: 'one',
    2: 'many',
}


class Query(object):

    _country = None
    _fallback = None
    _geoip = None
    _ip = None

    def __init__(self, fallback=None, ip=None, cell=None, wifi=None,
                 api_key=None, api_type=None, session=None,
                 http_session=None, geoip_db=None, stats_client=None):
        """
        A class representing a concrete query.

        :param fallback: A dictionary of fallback options.
        :type fallback: dict

        :param ip: An IP address, e.g. 127.0.0.1.
        :type ip: str

        :param cell: A list of cell query dicts.
        :type cell: list

        :param wifi: A list of wifi query dicts.
        :type wifi: list

        :param api_key: An ApiKey instance for the current query.
        :type api_key: :class:`ichnaea.models.api.ApiKey`

        :param api_type: The type of query API, for example `locate`.
        :type api_type: str

        :param session: An open database session.

        :param http_session: An open HTTP/S session.

        :param geoip_db: A geoip database.
        :type geoip_db: :class:`~ichnaea.geoip.GeoIPWrapper`

        :param stats_client: A stats client.
        :type stats_client: :class:`~ichnaea.log.StatsClient`
        """
        self.geoip_db = geoip_db
        self.http_session = http_session
        self.session = session
        self.stats_client = stats_client

        self.fallback = fallback
        self.ip = ip
        self.cell = cell
        self.wifi = wifi
        self.api_key = api_key
        if api_type not in (None, 'country', 'locate'):
            raise ValueError('Invalid api_type.')
        self.api_type = api_type

    @property
    def fallback(self):
        """
        A validated
        :class:`~ichnaea.api.locate.schema.FallbackLookup` instance.
        """
        return self._fallback

    @fallback.setter
    def fallback(self, values):
        if not values:
            values = {}
        valid = FallbackLookup.create(**values)
        if valid is None:  # pragma: no cover
            valid = FallbackLookup.create()
        self._fallback = valid

    @property
    def country(self):
        """
        The two letter country code of origin for this query.

        Can return None, if no country could be determined.
        """
        return self._country

    @property
    def geoip(self):
        """
        A GeoIP database entry for the originating IP address.

        Can return None if no database match could be found.
        """
        return self._geoip

    @property
    def ip(self):
        """The validated IP address."""
        return self._ip

    @ip.setter
    def ip(self, value):
        if not value:
            value = None
        try:
            valid = str(ip_address(value))
        except ValueError:
            valid = None
        self._ip = valid
        if valid:
            country = None
            geoip = None
            if self.geoip_db:
                geoip = self.geoip_db.geoip_lookup(valid)
                if geoip:
                    country = geoip.get('country_code')
                    if country:
                        country = country.upper()
            self._geoip = geoip
            self._country = country

    @property
    def cell(self):
        """
        The validated list of
        :class:`~ichnaea.api.locate.schema.CellLookup` instances.

        If the same cell network is supplied multiple times, this chooses only
        the best entry for each unique network.
        """
        return self._cell

    @property
    def cell_area(self):
        """
        The validated list of
        :class:`~ichnaea.api.locate.schema.CellAreaLookup` instances.

        If the same cell area is supplied multiple times, this chooses only
        the best entry for each unique area.
        """
        if self.fallback.lacf:
            return self._cell_area
        return []

    @cell.setter
    def cell(self, values):
        if not values:
            values = []
        values = list(values)
        self._cell_unvalidated = values

        filtered_areas = OrderedDict()
        filtered_cells = OrderedDict()
        for value in values:
            valid_area = CellAreaLookup.create(**value)
            if valid_area:
                existing = filtered_areas.get(valid_area.hashkey())
                if existing is not None and existing.better(valid_area):
                    pass
                else:
                    filtered_areas[valid_area.hashkey()] = valid_area
            valid_cell = CellLookup.create(**value)
            if valid_cell:
                existing = filtered_cells.get(valid_cell.hashkey())
                if existing is not None and existing.better(valid_cell):
                    pass
                else:
                    filtered_cells[valid_cell.hashkey()] = valid_cell
        self._cell_area = list(filtered_areas.values())
        self._cell = list(filtered_cells.values())

    @property
    def wifi(self):
        """
        The validated list of
        :class:`~ichnaea.api.locate.schema.WifiLookup` instances.

        If the same Wifi network is supplied multiple times, this chooses only
        the best entry for each unique network.

        If fewer than :data:`~ichnaea.api.locate.constants.MIN_WIFIS_IN_QUERY`
        unique valid Wifi networks are found, returns an empty list.
        """
        return self._wifi

    @wifi.setter
    def wifi(self, values):
        if not values:
            values = []
        values = list(values)
        self._wifi_unvalidated = values

        filtered = OrderedDict()
        for value in values:
            valid_wifi = WifiLookup.create(**value)
            if valid_wifi:
                existing = filtered.get(valid_wifi.mac)
                if existing is not None and existing.better(valid_wifi):
                    pass
                else:
                    filtered[valid_wifi.mac] = valid_wifi

        if len(filtered) < MIN_WIFIS_IN_QUERY:
            filtered = {}
        self._wifi = list(filtered.values())

    @property
    def expected_accuracy(self):
        accuracies = [DataAccuracy.none]

        if self.wifi:
            if self.api_type == 'country':
                accuracies.append(DataAccuracy.none)
            else:
                accuracies.append(DataAccuracy.high)
        if self.cell:
            if self.api_type == 'country':
                accuracies.append(DataAccuracy.low)
            else:
                accuracies.append(DataAccuracy.medium)
        if ((self.cell_area and self.fallback.lacf) or
                (self.ip and self.fallback.ipf)):
            accuracies.append(DataAccuracy.low)

        # return the best possible (smallest) accuracy
        return min(accuracies)

    def internal_query(self):
        """Returns a dictionary of this query in our internal format."""
        result = {}
        if self.cell:
            result['cell'] = []
            for cell in self.cell:
                cell_data = {}
                for field in cell._fields:
                    cell_data[field] = getattr(cell, field)
                result['cell'].append(cell_data)
        if self.wifi:
            result['wifi'] = []
            for wifi in self.wifi:
                wifi_data = {}
                for field in wifi._fields:
                    wifi_data[field] = getattr(wifi, field)
                result['wifi'].append(wifi_data)
        if self.fallback:
            fallback_data = {}
            for field in self.fallback._fields:
                fallback_data[field] = getattr(self.fallback, field)
            result['fallbacks'] = fallback_data
        return result

    def collect_metrics(self):
        """Should detailed metrics be collected for this query?"""
        allowed = bool(self.api_key and self.api_key.log and self.api_type)
        # don't report stats if there is really no data at all
        # in the query
        possible_result = bool(self.expected_accuracy != DataAccuracy.none)
        return allowed and possible_result

    def _emit_country_stat(self, metric, extra_tags):
        # Emit a country specific stat
        if not self.country:
            country = 'none'
        else:
            # TODO emit actual country based stats
            country = 'xx'

        metric = '%s.%s' % (self.api_type, metric)
        tags = [
            'key:%s' % self.api_key.name,
            'country:%s' % country,
        ]
        self.stats_client.incr(metric, tags=tags + extra_tags)

    def emit_query_stats(self):
        """Emit stats about the data contained in this query."""
        if not self.collect_metrics():
            return

        cells = len(self.cell)
        wifis = len(self._wifi_unvalidated)
        tags = []

        if not self.ip:
            tags.append('geoip:false')

        for name, length in (('cell', cells), ('wifi', wifis)):
            num = METRIC_MAPPING[min(length, 2)]
            tags.append('{name}:{num}'.format(name=name, num=num))
        self._emit_country_stat('query', tags)

    def emit_result_stats(self, result):
        """Emit stats about how well the result satisfied the query."""
        if not self.collect_metrics():
            return

        if self.api_type == 'country':
            # TODO: enable result stats for country API
            return

        if result.data_accuracy <= self.expected_accuracy:
            # equal or better / smaller accuracy
            status = 'hit'
        else:
            status = 'miss'

        tags = [
            'accuracy:%s' % self.expected_accuracy.name,
            'status:%s' % status,
        ]
        if status == 'hit' and result.source:
            tags.append('source:%s' % result.source.name)
        self._emit_country_stat('result', tags)

    def emit_source_stats(self, source, result):
        """Emit stats about how well the result satisfied the query."""
        if not self.collect_metrics():
            return

        if result.data_accuracy <= self.expected_accuracy:
            status = 'hit'
        else:
            status = 'miss'

        tags = [
            'source:%s' % source.name,
            'accuracy:%s' % self.expected_accuracy.name,
            'status:%s' % status,
        ]
        self._emit_country_stat('source', tags)
