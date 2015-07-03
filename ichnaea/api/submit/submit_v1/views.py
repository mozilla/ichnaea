from pyramid.httpexceptions import HTTPNoContent

from ichnaea.api.exceptions import JSONError
from ichnaea.api.submit.submit_v1.schema import SubmitV1Schema
from ichnaea.api.submit.views import BaseSubmitView
from ichnaea.models.transform import ReportTransform


class SubmitV1Transform(ReportTransform):

    time_id = 'time'

    position_id = (None, 'position')
    position_map = [
        ('lat', 'latitude'),
        ('lon', 'longitude'),
        'accuracy',
        'altitude',
        ('altitude_accuracy', 'altitudeAccuracy'),
        'age',
        'heading',
        'pressure',
        'speed',
        'source',
    ]

    radio_id = ('radio', 'radioType')
    cell_id = ('cell', 'cellTowers')
    cell_map = [
        ('radio', 'radioType'),
        ('mcc', 'mobileCountryCode'),
        ('mnc', 'mobileNetworkCode'),
        ('lac', 'locationAreaCode'),
        ('cid', 'cellId'),
        'age',
        'asu',
        ('psc', 'primaryScramblingCode'),
        'serving',
        ('signal', 'signalStrength'),
        ('ta', 'timingAdvance'),
    ]

    wifi_id = ('wifi', 'wifiAccessPoints')
    wifi_map = [
        # ssid is not mapped on purpose, we never want to store it
        ('key', 'macAddress'),
        'age',
        'channel',
        'frequency',
        ('radio', 'radioType'),
        ('signal', 'signalStrength'),
        'signalToNoiseRatio',
    ]


class SubmitV1View(BaseSubmitView):

    error_response = JSONError
    route = '/v1/submit'
    schema = SubmitV1Schema
    transform = SubmitV1Transform
    view_name = 'submit'

    def success(self):
        return HTTPNoContent()
