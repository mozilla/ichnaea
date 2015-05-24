from pyramid.httpexceptions import (
    HTTPOk,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.models.transform import ReportTransform
from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import BaseSubmitter
from ichnaea.service.error import JSONParseError
from ichnaea.service.geosubmit2.schema import GeoSubmit2BatchSchema


def configure_geosubmit2(config):
    config.add_route('v2_geosubmit', '/v2/geosubmit')
    config.add_view(geosubmit2_view,
                    route_name='v2_geosubmit', renderer='json')


class GeoSubmit2Transform(ReportTransform):
    # the connection section is not mapped on purpose

    toplevel_map = [
        ('carrier', 'carrier', None),
        ('homeMobileCountryCode', 'homeMobileCountryCode', None),
        ('homeMobileNetworkCode', 'homeMobileNetworkCode', None),
    ]

    position_id = ('position', 'position')
    position_map = [
        ('latitude', 'latitude', None),
        ('longitude', 'longitude', None),
        ('accuracy', 'accuracy', None),
        ('altitude', 'altitude', None),
        ('altitudeAccuracy', 'altitudeAccuracy', None),
        ('age', 'age', None),
        ('heading', 'heading', None),
        ('pressure', 'pressure', None),
        ('speed', 'speed', None),
        ('source', 'source', None),
    ]

    blue_id = ('bluetoothBeacons', 'bluetoothBeacons')
    blue_map = [
        ('macAddress', 'macAddress', None),
        ('name', 'name', None),
        ('age', 'age', None),
        ('signalStrength', 'signalStrength', None),
    ]

    cell_id = ('cellTowers', 'cellTowers')
    cell_map = [
        ('radioType', 'radioType', None),
        ('mobileCountryCode', 'mobileCountryCode', None),
        ('mobileNetworkCode', 'mobileNetworkCode', None),
        ('locationAreaCode', 'locationAreaCode', None),
        ('cellId', 'cellId', None),
        ('age', 'age', None),
        ('asu', 'asu', None),
        ('primaryScramblingCode', 'primaryScramblingCode', None),
        ('serving', 'serving', None),
        ('signalStrength', 'signalStrength', None),
        ('timingAdvance', 'timingAdvance', None),
    ]

    wifi_id = ('wifiAccessPoints', 'wifiAccessPoints')
    wifi_map = [
        ('macAddress', 'macAddress', None),
        # ssid is not mapped on purpose, we never want to store it
        ('radioType', 'radioType', None),
        ('age', 'age', None),
        ('channel', 'channel', None),
        ('frequency', 'frequency', None),
        ('signalToNoiseRatio', 'signalToNoiseRatio', None),
        ('signalStrength', 'signalStrength', None),
    ]

    def _parse_extra(self, item, report):
        self._parse_timestamp(item, report)


class GeoSubmitter2(BaseSubmitter):

    schema = GeoSubmit2BatchSchema
    error_response = JSONParseError

    def prepare_reports(self, request_data):
        transform = GeoSubmit2Transform()
        return transform.transform(request_data['items'])


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
