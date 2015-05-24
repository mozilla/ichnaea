import time

from pyramid.httpexceptions import (
    HTTPOk,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import BaseSubmitter
from ichnaea.service.error import JSONParseError
from ichnaea.service.geosubmit2.schema import GeoSubmit2BatchSchema


def configure_geosubmit2(config):
    config.add_route('v2_geosubmit', '/v2/geosubmit')
    config.add_view(geosubmit2_view,
                    route_name='v2_geosubmit', renderer='json')


class GeoSubmitter2(BaseSubmitter):

    schema = GeoSubmit2BatchSchema
    error_response = JSONParseError

    # the connection section is not mapped on purpose

    toplevel_map = [
        ('carrier', 'carrier', None),
        ('homeMobileCountryCode', 'homeMobileCountryCode', None),
        ('homeMobileNetworkCode', 'homeMobileNetworkCode', None),
    ]

    position_map = [
        ('latitude', 'latitude', None),
        ('longitude', 'longitude', None),
        ('accuracy', 'accuracy', 0),
        ('altitude', 'altitude', 0),
        ('altitudeAccuracy', 'altitudeAccuracy', 0),
        ('age', 'age', None),
        ('heading', 'heading', -1.0),
        ('pressure', 'pressure', None),
        ('speed', 'speed', -1.0),
        ('source', 'source', 'gps'),
    ]

    blue_map = [
        ('macAddress', 'macAddress', None),
        ('name', 'name', None),
        ('age', 'age', None),
        ('signalStrength', 'signalStrength', None),
    ]

    cell_map = [
        ('radioType', 'radioType', None),
        ('mobileCountryCode', 'mobileCountryCode', None),
        ('mobileNetworkCode', 'mobileNetworkCode', None),
        ('locationAreaCode', 'locationAreaCode', None),
        ('cellId', 'cellId', None),
        ('age', 'age', 0),
        ('asu', 'asu', -1),
        ('primaryScramblingCode', 'primaryScramblingCode', -1),
        ('serving', 'serving', None),
        ('signalStrength', 'signalStrength', 0),
        ('timingAdvance', 'timingAdvance', 0),
    ]

    wifi_map = [
        ('macAddress', 'macAddress', None),
        # ssid is not mapped on purpose, we never want to store it
        ('radioType', 'radioType', None),
        ('age', 'age', 0),
        ('channel', 'channel', 0),
        ('frequency', 'frequency', 0),
        ('signalToNoiseRatio', 'signalToNoiseRatio', 0),
        ('signalStrength', 'signalStrength', 0),
    ]

    def conditional_set(self, item, target, value, missing):
        if value != missing:
            item[target] = value

    def _parse_blues(self, item, report):
        blues = []
        for blue_item in item['bluetoothBeacons']:
            blue = {}
            for target, source, missing in self.blue_map:
                self.conditional_set(blue, target,
                                     blue_item[source], missing)
            if blue:
                blues.append(blue)
        if blues:
            report['bluetoothBeacons'] = blues
        return blues

    def _parse_cells(self, item, report):
        cells = []
        item_radio = item['radioType']
        for cell_item in item['cellTowers']:
            cell = {}
            for target, source, missing in self.cell_map:
                self.conditional_set(cell, target,
                                     cell_item[source], missing)
            if cell:
                if 'radioType' not in cell and item_radio:
                    cell['radioType'] = item_radio
                if cell.get('radioType') == 'umts':
                    cell['radioType'] = 'wcdma'
                cells.append(cell)
        if cells:
            report['cellTowers'] = cells
        return cells

    def _parse_position(self, item, report):
        position = {}
        item_position = item.get('position')
        if item_position:
            for target, source, missing in self.position_map:
                self.conditional_set(position, target,
                                     item_position[source], missing)
        report['position'] = position
        return position

    def _parse_toplevel(self, item, report):
        if item['timestamp'] == 0:
            report['timestamp'] = time.time() * 1000.0
        else:
            report['timestamp'] = item['timestamp']

        for target, source, missing in self.toplevel_map:
            self.conditional_set(report, target, item[source], missing)
        return report

    def _parse_wifis(self, item, report):
        wifis = []
        for wifi_item in item['wifiAccessPoints']:
            wifi = {}
            for target, source, missing in self.wifi_map:
                self.conditional_set(wifi, target,
                                     wifi_item[source], missing)
            if wifi:
                wifis.append(wifi)
        if wifis:
            report['wifiAccessPoints'] = wifis
        return wifis

    def prepare_reports(self, request_data):
        reports = []
        for item in request_data['items']:
            report = {}
            self._parse_toplevel(item, report)
            blues = self._parse_blues(item, report)
            cells = self._parse_cells(item, report)
            position = self._parse_position(item, report)
            wifis = self._parse_wifis(item, report)

            if blues or cells or position or wifis:
                reports.append(report)

        return reports


@check_api_key('geosubmit2', error_on_invalidkey=False)
def geosubmit2_view(request, api_key):
    submitter = GeoSubmitter2(request, api_key)

    # may raise HTTP error
    request_data = submitter.preprocess()

    try:
        submitter.submit(request_data)
    except ConnectionError:  # pragma: no cover
        return HTTPServiceUnavailable()

    result = HTTPOk()
    result.content_type = 'application/json'
    result.body = '{}'
    return result
