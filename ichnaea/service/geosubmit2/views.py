from ichnaea.models.transform import ReportTransform
from ichnaea.service.base_submit import BaseSubmitView
from ichnaea.service.geosubmit2.schema import GeoSubmit2Schema


def configure_geosubmit2(config):
    config.add_route('v2_geosubmit', '/v2/geosubmit')
    config.add_view(GeoSubmit2View,
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


class GeoSubmit2View(BaseSubmitView):

    schema = GeoSubmit2Schema
    transform = GeoSubmit2Transform
    view_name = 'geosubmit2'
