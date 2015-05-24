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

    time_id = 'timestamp'
    toplevel_map = [
        ('carrier', 'carrier'),
        ('homeMobileCountryCode', 'homeMobileCountryCode'),
        ('homeMobileNetworkCode', 'homeMobileNetworkCode'),
    ]

    position_id = ('position', 'position')
    position_map = [
        ('latitude', 'latitude'),
        ('longitude', 'longitude'),
        ('accuracy', 'accuracy'),
        ('altitude', 'altitude'),
        ('altitudeAccuracy', 'altitudeAccuracy'),
        ('age', 'age'),
        ('heading', 'heading'),
        ('pressure', 'pressure'),
        ('speed', 'speed'),
        ('source', 'source'),
    ]

    blue_id = ('bluetoothBeacons', 'bluetoothBeacons')
    blue_map = [
        ('macAddress', 'macAddress'),
        ('name', 'name'),
        ('age', 'age'),
        ('signalStrength', 'signalStrength'),
    ]

    radio_id = ('radioType', 'radioType')
    cell_id = ('cellTowers', 'cellTowers')
    cell_map = [
        ('radioType', 'radioType'),
        ('mobileCountryCode', 'mobileCountryCode'),
        ('mobileNetworkCode', 'mobileNetworkCode'),
        ('locationAreaCode', 'locationAreaCode'),
        ('cellId', 'cellId'),
        ('age', 'age'),
        ('asu', 'asu'),
        ('primaryScramblingCode', 'primaryScramblingCode'),
        ('serving', 'serving'),
        ('signalStrength', 'signalStrength'),
        ('timingAdvance', 'timingAdvance'),
    ]

    wifi_id = ('wifiAccessPoints', 'wifiAccessPoints')
    wifi_map = [
        # ssid is not mapped on purpose, we never want to store it
        ('macAddress', 'macAddress'),
        ('radioType', 'radioType'),
        ('age', 'age'),
        ('channel', 'channel'),
        ('frequency', 'frequency'),
        ('signalToNoiseRatio', 'signalToNoiseRatio'),
        ('signalStrength', 'signalStrength'),
    ]


class GeoSubmitter2(BaseSubmitter):

    error_response = JSONParseError
    schema = GeoSubmit2BatchSchema
    transform = GeoSubmit2Transform


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
