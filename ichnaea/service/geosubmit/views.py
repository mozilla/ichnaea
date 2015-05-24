from pyramid.httpexceptions import (
    HTTPOk,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.models.transform import ReportTransform
from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import BaseSubmitter
from ichnaea.service.error import JSONParseError
from ichnaea.service.geosubmit.schema import GeoSubmitBatchSchema


def configure_geosubmit(config):
    config.add_route('v1_geosubmit', '/v1/geosubmit')
    config.add_view(geosubmit_view, route_name='v1_geosubmit', renderer='json')


class GeoSubmitTransform(ReportTransform):

    time_id = 'timestamp'
    toplevel_map = [
        ('carrier', 'carrier'),
        ('homeMobileCountryCode', 'homeMobileCountryCode'),
        ('homeMobileNetworkCode', 'homeMobileNetworkCode'),
    ]

    position_id = (None, 'position')
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
        ('psc', 'primaryScramblingCode'),
        ('serving', 'serving'),
        ('signalStrength', 'signalStrength'),
        ('timingAdvance', 'timingAdvance'),
    ]

    wifi_id = ('wifiAccessPoints', 'wifiAccessPoints')
    wifi_map = [
        ('macAddress', 'macAddress'),
        ('age', 'age'),
        ('channel', 'channel'),
        ('frequency', 'frequency'),
        ('radioType', 'radioType'),
        ('signalToNoiseRatio', 'signalToNoiseRatio'),
        ('signalStrength', 'signalStrength'),
        # ssid is not mapped on purpose, we never want to store it
    ]


class GeoSubmitter(BaseSubmitter):

    error_response = JSONParseError
    schema = GeoSubmitBatchSchema
    transform = GeoSubmitTransform


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
