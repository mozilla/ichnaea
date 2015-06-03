from ichnaea.models.transform import ReportTransform
from ichnaea.api.submit.base_submit import BaseSubmitView
from ichnaea.api.submit.submit_v3.schema import SubmitV3Schema


class SubmitV3Transform(ReportTransform):
    # the connection section is not mapped on purpose

    time_id = 'timestamp'
    toplevel_map = [
        'carrier',
        'homeMobileCountryCode',
        'homeMobileNetworkCode',
    ]

    position_id = ('position', 'position')
    position_map = [
        'latitude',
        'longitude',
        'accuracy',
        'altitude',
        'altitudeAccuracy',
        'age',
        'heading',
        'pressure',
        'speed',
        'source',
    ]

    blue_id = ('bluetoothBeacons', 'bluetoothBeacons')
    blue_map = [
        'macAddress',
        'name',
        'age',
        'signalStrength',
    ]

    radio_id = ('radioType', 'radioType')
    cell_id = ('cellTowers', 'cellTowers')
    cell_map = [
        'radioType',
        'mobileCountryCode',
        'mobileNetworkCode',
        'locationAreaCode',
        'cellId',
        'age',
        'asu',
        'primaryScramblingCode',
        'serving',
        'signalStrength',
        'timingAdvance',
    ]

    wifi_id = ('wifiAccessPoints', 'wifiAccessPoints')
    wifi_map = [
        # ssid is not mapped on purpose, we never want to store it
        'macAddress',
        'radioType',
        'age',
        'channel',
        'frequency',
        'signalToNoiseRatio',
        'signalStrength',
    ]


class SubmitV3View(BaseSubmitView):

    route = '/v2/geosubmit'
    schema = SubmitV3Schema
    transform = SubmitV3Transform
    view_name = 'geosubmit2'
