from pyramid.httpexceptions import (
    HTTPNoContent,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.models.transform import ReportTransform
from ichnaea.service.error import JSONError
from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import BaseSubmitter
from ichnaea.service.submit.schema import SubmitSchema


def configure_submit(config):
    config.add_route('v1_submit', '/v1/submit')
    config.add_view(submit_view, route_name='v1_submit', renderer='json')


class SubmitTransform(ReportTransform):

    time_id = 'time'

    position_id = (None, 'position')
    position_map = [
        ('lat', 'latitude', None),
        ('lon', 'longitude', None),
        ('accuracy', 'accuracy', None),
        ('altitude', 'altitude', None),
        ('altitude_accuracy', 'altitudeAccuracy', None),
        ('age', 'age', None),
        ('heading', 'heading', None),
        ('pressure', 'pressure', None),
        ('speed', 'speed', None),
        ('source', 'source', None),
    ]

    radio_id = ('radio', 'radioType')
    cell_id = ('cell', 'cellTowers')
    cell_map = [
        ('radio', 'radioType', None),
        ('mcc', 'mobileCountryCode', None),
        ('mnc', 'mobileNetworkCode', None),
        ('lac', 'locationAreaCode', None),
        ('cid', 'cellId', None),
        ('age', 'age', None),
        ('asu', 'asu', None),
        ('psc', 'primaryScramblingCode', None),
        ('serving', 'serving', None),
        ('signal', 'signalStrength', None),
        ('ta', 'timingAdvance', None),
    ]

    wifi_id = ('wifi', 'wifiAccessPoints')
    wifi_map = [
        ('key', 'macAddress', None),
        ('age', 'age', None),
        ('channel', 'channel', None),
        ('frequency', 'frequency', None),
        ('radio', 'radioType', None),
        ('signal', 'signalStrength', None),
        ('signalToNoiseRatio', 'signalToNoiseRatio', None),
    ]


class Submitter(BaseSubmitter):

    schema = SubmitSchema
    error_response = JSONError

    def prepare_reports(self, request_data):
        transform = SubmitTransform()
        return transform.transform_many(request_data['items'])


@check_api_key('submit', error_on_invalidkey=False)
def submit_view(request, api_key):
    submitter = Submitter(request, api_key)

    # may raise HTTP error
    request_data = submitter.preprocess()

    try:
        submitter.submit(request_data)
    except ConnectionError:  # pragma: no cover
        return HTTPServiceUnavailable()

    return HTTPNoContent()
