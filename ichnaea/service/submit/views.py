from pyramid.httpexceptions import HTTPNoContent

from ichnaea.models.transform import ReportTransform
from ichnaea.service.error import JSONError
from ichnaea.service.base_submit import BaseSubmitView
from ichnaea.service.submit.schema import SubmitSchema


class SubmitTransform(ReportTransform):

    time_id = 'time'

    position_id = (None, 'position')
    position_map = [
        ('lat', 'latitude'),
        ('lon', 'longitude'),
        ('accuracy', 'accuracy'),
        ('altitude', 'altitude'),
        ('altitude_accuracy', 'altitudeAccuracy'),
        ('age', 'age'),
        ('heading', 'heading'),
        ('pressure', 'pressure'),
        ('speed', 'speed'),
        ('source', 'source'),
    ]

    radio_id = ('radio', 'radioType')
    cell_id = ('cell', 'cellTowers')
    cell_map = [
        ('radio', 'radioType'),
        ('mcc', 'mobileCountryCode'),
        ('mnc', 'mobileNetworkCode'),
        ('lac', 'locationAreaCode'),
        ('cid', 'cellId'),
        ('age', 'age'),
        ('asu', 'asu'),
        ('psc', 'primaryScramblingCode'),
        ('serving', 'serving'),
        ('signal', 'signalStrength'),
        ('ta', 'timingAdvance'),
    ]

    wifi_id = ('wifi', 'wifiAccessPoints')
    wifi_map = [
        # ssid is not mapped on purpose, we never want to store it
        ('key', 'macAddress'),
        ('age', 'age'),
        ('channel', 'channel'),
        ('frequency', 'frequency'),
        ('radio', 'radioType'),
        ('signal', 'signalStrength'),
        ('signalToNoiseRatio', 'signalToNoiseRatio'),
    ]


class SubmitView(BaseSubmitView):

    error_response = JSONError
    route = '/v1/submit'
    schema = SubmitSchema
    transform = SubmitTransform
    view_name = 'submit'

    def success(self):
        return HTTPNoContent()
