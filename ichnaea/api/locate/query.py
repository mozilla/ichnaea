"""Code representing a query."""

from ipaddress import ip_address
import markus

from ichnaea.api.locate.constants import (
    DataAccuracy,
    MIN_BLUES_IN_QUERY,
    MIN_WIFIS_IN_QUERY,
)
from ichnaea.api.locate.schema import (
    BlueLookup,
    CellAreaLookup,
    CellLookup,
    FallbackLookup,
    WifiLookup,
)

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

METRIC_MAPPING = {0: "none", 1: "one", 2: "many"}
METRICS = markus.get_metrics()


class Query(object):

    _fallback = None
    _geoip = None
    _ip = None
    _region = None

    def __init__(
        self,
        fallback=None,
        ip=None,
        blue=None,
        cell=None,
        wifi=None,
        api_key=None,
        api_type=None,
        session=None,
        http_session=None,
        geoip_db=None,
    ):
        """
        A class representing a concrete query.

        :param fallback: A dictionary of fallback options.
        :type fallback: dict

        :param ip: An IP address, e.g. 127.0.0.1.
        :type ip: str

        :param blue: A list of bluetooth query dicts.
        :type blue: list

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

        """
        self.geoip_db = geoip_db
        self.http_session = http_session
        self.session = session

        self.fallback = fallback
        self.ip = ip
        self.blue = blue
        self.cell = cell
        self.wifi = wifi
        self.api_key = api_key
        if api_type not in (None, "region", "locate"):
            raise ValueError("Invalid api_type.")
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
        if valid is None:
            valid = FallbackLookup.create()
        self._fallback = valid

    @property
    def geoip(self):
        """
        A GeoIP database entry for the originating IP address.

        Can return None if no database match could be found.
        """
        return self._geoip

    @property
    def geoip_only(self):
        """Did the query contain only GeoIP data?"""
        if self.blue or self.cell or self.cell_area or self.wifi:
            return False
        if self.geoip:
            return True
        return None

    @property
    def ip(self):
        """The validated IP address."""
        return self._ip

    @ip.setter
    def ip(self, value):
        if not value:
            value = None
        elif isinstance(value, bytes):
            value = value.decode("ascii", "ignore")
        try:
            valid = str(ip_address(value))
        except ValueError:
            valid = None
        self._ip = valid
        if valid:
            region = None
            geoip = None
            if self.geoip_db:
                geoip = self.geoip_db.lookup(valid)
                if geoip:
                    region = geoip.get("region_code")
            self._geoip = geoip
            self._region = region

    @property
    def region(self):
        """
        The two letter region code of origin for this query.

        Can return None, if no region could be determined.
        """
        return self._region

    @property
    def blue(self):
        """
        The validated list of
        :class:`~ichnaea.api.locate.schema.BlueLookup` instances.

        If the same Bluetooth network is supplied multiple times, this
        chooses only the best entry for each unique network.

        If fewer than :data:`~ichnaea.api.locate.constants.MIN_BLUSS_IN_QUERY`
        unique valid Bluetooth networks are found, returns an empty list.
        """
        return self._blue

    @blue.setter
    def blue(self, values):
        if not values:
            values = []
        values = list(values)
        self._blue_unvalidated = values

        filtered = OrderedDict()
        for value in values:
            valid_blue = BlueLookup.create(**value)
            if valid_blue:
                existing = filtered.get(valid_blue.macAddress)
                if existing is not None and existing.better(valid_blue):
                    pass
                else:
                    filtered[valid_blue.macAddress] = valid_blue

        if len(filtered) < MIN_BLUES_IN_QUERY:
            filtered = {}
        self._blue = list(filtered.values())

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
                areaid = valid_area.areaid
                existing = filtered_areas.get(areaid)
                if existing is not None and existing.better(valid_area):
                    pass
                else:
                    filtered_areas[areaid] = valid_area
            valid_cell = CellLookup.create(**value)
            if valid_cell:
                cellid = valid_cell.cellid
                existing = filtered_cells.get(cellid)
                if existing is not None and existing.better(valid_cell):
                    pass
                else:
                    filtered_cells[cellid] = valid_cell
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
                existing = filtered.get(valid_wifi.macAddress)
                if existing is not None and existing.better(valid_wifi):
                    pass
                else:
                    filtered[valid_wifi.macAddress] = valid_wifi

        if len(filtered) < MIN_WIFIS_IN_QUERY:
            filtered = {}
        self._wifi = list(filtered.values())

    @property
    def expected_accuracy(self):
        accuracies = [DataAccuracy.none]

        if self.api_type == "region":
            if self.blue or self.cell or self.wifi:
                accuracies.append(DataAccuracy.low)
        else:
            if self.cell:
                accuracies.append(DataAccuracy.medium)
            if self.blue or self.wifi:
                accuracies.append(DataAccuracy.high)

        if (self.cell_area and self.fallback.lacf) or (self.ip and self.fallback.ipf):
            accuracies.append(DataAccuracy.low)

        # return the best possible (smallest) accuracy
        return min(accuracies)

    def json(self):
        """Returns a JSON representation of this query."""
        result = {}
        if self.blue:
            result["bluetoothBeacons"] = [blue.json() for blue in self.blue]
        if self.cell:
            result["cellTowers"] = [cell.json() for cell in self.cell]
        if self.wifi:
            result["wifiAccessPoints"] = [wifi.json() for wifi in self.wifi]
        if self.fallback:
            result["fallbacks"] = self.fallback.json()
        return result

    def networks(self):
        """Returns networks seen in the validated query."""
        result = {"area": set(), "blue": set(), "cell": set(), "wifi": set()}
        if self.cell_area:
            result["area"] = set([c.areaid for c in self.cell_area])
        if self.blue:
            result["blue"] = set([b.mac for b in self.blue])
        if self.cell:
            result["cell"] = set([c.cellid for c in self.cell])
        if self.wifi:
            result["wifi"] = set([w.mac for w in self.wifi])
        return result

    def collect_metrics(self):
        """Should detailed metrics be collected for this query?"""
        allowed = bool(self.api_key and self.api_key.valid_key)
        # don't report stats if there is no data at all in the query
        possible_result = bool(self.expected_accuracy != DataAccuracy.none)
        return allowed and possible_result

    def _emit_stat(self, metric, extra_tags):
        metric = "%s.%s" % (self.api_type, metric)
        tags = ["key:%s" % self.api_key.valid_key]
        METRICS.incr(metric, tags=tags + extra_tags)

    def emit_query_stats(self):
        """Emit stats about the data contained in this query."""
        if not self.collect_metrics():
            return

        blues = len(self._blue_unvalidated)
        cells = len(self.cell)
        wifis = len(self._wifi_unvalidated)
        tags = []

        if not self.ip:
            tags.append("geoip:false")

        for name, length in (("blue", blues), ("cell", cells), ("wifi", wifis)):
            num = METRIC_MAPPING[min(length, 2)]
            tags.append("{name}:{num}".format(name=name, num=num))
        self._emit_stat("query", tags)

    def emit_result_stats(self, result):
        """Emit stats about how well the result satisfied the query."""
        if not self.collect_metrics():
            return

        allow_fallback = str(
            bool(self.api_key and self.api_key.can_fallback() or False)
        ).lower()

        if result is None:
            data_accuracy = DataAccuracy.none
            source = None
        else:
            data_accuracy = result.data_accuracy
            source = result.source

        status = "miss"
        if data_accuracy <= self.expected_accuracy:
            # equal or better / smaller accuracy
            status = "hit"

        tags = [
            "fallback_allowed:%s" % allow_fallback,
            "accuracy:%s" % self.expected_accuracy.name,
            "status:%s" % status,
        ]
        if status == "hit" and source:
            tags.append("source:%s" % source.name)
        self._emit_stat("result", tags)

    def emit_source_stats(self, source, results):
        """Emit stats about how well the source satisfied the query."""
        if not self.collect_metrics():
            return

        # If any one of the results was good enough, consider it a hit.
        status = "miss"
        for result in results:
            if result.data_accuracy <= self.expected_accuracy:
                # equal or better / smaller accuracy
                status = "hit"
                break

        tags = [
            "source:%s" % source.name,
            "accuracy:%s" % self.expected_accuracy.name,
            "status:%s" % status,
        ]
        self._emit_stat("source", tags)
