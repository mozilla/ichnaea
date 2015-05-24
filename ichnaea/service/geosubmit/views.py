import time

from pyramid.httpexceptions import (
    HTTPOk,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import BaseSubmitter
from ichnaea.service.error import JSONParseError
from ichnaea.service.geosubmit.schema import GeoSubmitBatchSchema


def configure_geosubmit(config):
    config.add_route('v1_geosubmit', '/v1/geosubmit')
    config.add_view(geosubmit_view, route_name='v1_geosubmit', renderer='json')


class GeoSubmitter(BaseSubmitter):

    schema = GeoSubmitBatchSchema
    error_response = JSONParseError

    def prepare_reports(self, request_data):
        def conditional_set(item, target, value, missing):
            if value != missing:
                item[target] = value

        position_map = [
            ('latitude', 'latitude', None),
            ('longitude', 'longitude', None),
            ('accuracy', 'accuracy', 0),
            ('altitude', 'altitude', 0),
            ('altitudeAccuracy', 'altitudeAccuracy', 0),
            ('age', 'age', None),
            ('carrier', 'carrier', None),
            ('heading', 'heading', -1.0),
            ('homeMobileCountryCode', 'homeMobileCountryCode', None),
            ('homeMobileNetworkCode', 'homeMobileNetworkCode', None),
            ('pressure', 'pressure', None),
            ('speed', 'speed', -1.0),
            ('source', 'source', 'gps'),
        ]

        cell_map = [
            ('radioType', 'radioType', None),
            ('mobileCountryCode', 'mobileCountryCode', None),
            ('mobileNetworkCode', 'mobileNetworkCode', None),
            ('locationAreaCode', 'locationAreaCode', None),
            ('cellId', 'cellId', None),
            ('age', 'age', 0),
            ('asu', 'asu', -1),
            ('primaryScramblingCode', 'psc', -1),
            ('serving', 'serving', None),
            ('signalStrength', 'signalStrength', 0),
            ('timingAdvance', 'timingAdvance', 0),
        ]

        wifi_map = [
            ('macAddress', 'macAddress', None),
            ('radioType', 'radioType', None),
            ('age', 'age', 0),
            ('channel', 'channel', 0),
            ('frequency', 'frequency', 0),
            ('signalToNoiseRatio', 'signalToNoiseRatio', 0),
            ('signalStrength', 'signalStrength', 0),
        ]

        reports = []
        for item in request_data['items']:
            report = {}

            if item['timestamp'] == 0:
                report['timestamp'] = time.time() * 1000.0
            else:
                report['timestamp'] = item['timestamp']

            position = {}
            for target, source, missing in position_map:
                conditional_set(position, target, item[source], missing)
            if position:
                report['position'] = position

            cells = []
            item_radio = item['radioType']
            for cell_item in item['cellTowers']:
                cell = {}
                for target, source, missing in cell_map:
                    conditional_set(cell, target, cell_item[source], missing)
                if cell:
                    if 'radioType' not in cell and item_radio:
                        cell['radioType'] = item_radio
                    if cell.get('radioType') == 'umts':
                        cell['radioType'] = 'wcdma'
                    cells.append(cell)

            if cells:
                report['cellTowers'] = cells

            wifis = []
            for wifi_item in item['wifiAccessPoints']:
                wifi = {}
                for target, source, missing in wifi_map:
                    conditional_set(wifi, target, wifi_item[source], missing)
                if wifi:
                    wifis.append(wifi)

            if wifis:
                report['wifiAccessPoints'] = wifis

            if cells or wifis:
                reports.append(report)

        return reports


@check_api_key('geosubmit', error_on_invalidkey=False)
def geosubmit_view(request, api_key):
    submitter = GeoSubmitter(request, api_key)

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
