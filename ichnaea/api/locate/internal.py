"""Implementation of a search source based on our internal data."""

from ichnaea.api.locate.blue import BluePositionMixin, BlueRegionMixin
from ichnaea.api.locate.cell import CellPositionMixin, CellRegionMixin
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import PositionSource, RegionSource
from ichnaea.api.locate.wifi import WifiPositionMixin, WifiRegionMixin


class BaseInternalSource(object):
    """A source based on our own crowd-sourced internal data."""

    fallback_field = None
    source = DataSource.internal

    def should_search(self, query, results):
        if not super(BaseInternalSource, self).should_search(query, results):
            return False
        if not (
            self.should_search_blue(query, results)
            or self.should_search_cell(query, results)
            or self.should_search_wifi(query, results)
        ):
            return False
        return True

    def search(self, query):
        results = self.result_list()

        for should, search in (
            # Search by most precise to least precise data type.
            (self.should_search_blue, self.search_blue),
            (self.should_search_wifi, self.search_wifi),
            (self.should_search_cell, self.search_cell),
        ):

            if should(query, results):
                results.add(search(query))

        query.emit_source_stats(self.source, results)
        return results


class InternalPositionSource(
    BaseInternalSource,
    BluePositionMixin,
    CellPositionMixin,
    WifiPositionMixin,
    PositionSource,
):
    """A position source based on our own crowd-sourced internal data."""

    GLOBAL_RATE_KEY = "global_locate_sample_rate"

    def _store_query(self, query, results):
        best_result = results.best()
        if not best_result:
            return

        result_networks = {"area": set(), "blue": set(), "cell": set(), "wifi": set()}
        for net_type, net_id, seen_today in best_result.used_networks:
            if seen_today:
                # only add network if it was last_seen today
                result_networks[net_type].add(net_id)

        if result_networks == query.networks():
            # don't store queries, based exclusively on data,
            # which was already validated today
            return

        raw_global_rate = self.redis_client.get(self.GLOBAL_RATE_KEY)
        global_rate = float(raw_global_rate or 100.0)
        if not query.api_key.store_sample("locate", global_rate):
            # only store some percentage of the requests
            return

        report = query.json()
        report.update(best_result.json())

        data = [
            {
                "api_key": query.api_key.valid_key,
                "source": report["position"]["source"],
                "report": report,
            }
        ]

        try:
            self.data_queues["update_incoming"].enqueue(data)
        except Exception:
            self.raven_client.captureException()

    def search(self, query):
        results = super(InternalPositionSource, self).search(query)
        self._store_query(query, results)
        return results


class InternalRegionSource(
    BaseInternalSource, BlueRegionMixin, CellRegionMixin, WifiRegionMixin, RegionSource
):
    """A region source based on our own crowd-sourced internal data."""
