from ichnaea.models.transform import ReportTransform
from ichnaea.service.base_submit import BaseSubmitView
from ichnaea.service.geosubmit.schema import GeoSubmitSchema


def configure_geosubmit(config):
    config.add_route('v1_geosubmit', '/v1/geosubmit')
    config.add_view(GeoSubmitView, route_name='v1_geosubmit', renderer='json')


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
        # ssid is not mapped on purpose, we never want to store it
        ('macAddress', 'macAddress'),
        ('age', 'age'),
        ('channel', 'channel'),
        ('frequency', 'frequency'),
        ('radioType', 'radioType'),
        ('signalToNoiseRatio', 'signalToNoiseRatio'),
        ('signalStrength', 'signalStrength'),
    ]


class GeoSubmitView(BaseSubmitView):

    schema = GeoSubmitSchema
    transform = GeoSubmitTransform
    view_name = 'geosubmit'
