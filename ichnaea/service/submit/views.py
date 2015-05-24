from pyramid.httpexceptions import (
    HTTPNoContent,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.models.transform import ReportTransform
from ichnaea.service.error import JSONError
from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import (
    BaseSubmitter,
    BaseSubmitView,
)
from ichnaea.service.submit.schema import SubmitSchema


def configure_submit(config):
    config.add_route('v1_submit', '/v1/submit')
    config.add_view(SubmitView, route_name='v1_submit', renderer='json')


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
        ('key', 'macAddress'),
        ('age', 'age'),
        ('channel', 'channel'),
        ('frequency', 'frequency'),
        ('radio', 'radioType'),
        ('signal', 'signalStrength'),
        ('signalToNoiseRatio', 'signalToNoiseRatio'),
    ]


class SubmitView(BaseSubmitView):

    class Submitter(BaseSubmitter):

        error_response = JSONError
        schema = SubmitSchema
        transform = SubmitTransform

    @check_api_key('submit', error_on_invalidkey=False)
    def __call__(self, api_key):
        submitter = self.Submitter(self.request, api_key)

        # may raise HTTP error
        request_data = submitter.preprocess()

        try:
            submitter.submit(request_data)
        except ConnectionError:  # pragma: no cover
            return HTTPServiceUnavailable()

        return HTTPNoContent()
