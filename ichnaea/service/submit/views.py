from pyramid.httpexceptions import (
    HTTPNoContent,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.service.error import JSONError
from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import BaseSubmitter
from ichnaea.service.submit.schema import SubmitSchema


def configure_submit(config):
    config.add_route('v1_submit', '/v1/submit')
    config.add_view(submit_view, route_name='v1_submit', renderer='json')


class Submitter(BaseSubmitter):

    schema = SubmitSchema
    error_response = JSONError

    def prepare_measure_data(self, request_data):
        reports = []
        for item in request_data['items']:
            report = item.copy()
            report_radio = report['radio']
            for cell in report['cell']:
                if cell['radio'] is None:
                    cell['radio'] = report_radio
            reports.append(report)
            if 'radio' in report:
                del report['radio']
        return reports


@check_api_key('submit', error_on_invalidkey=False)
def submit_view(request):
    submitter = Submitter(request)

    # may raise HTTP error
    request_data = submitter.preprocess()

    try:
        submitter.insert_measures(request_data)
    except ConnectionError:  # pragma: no cover
        return HTTPServiceUnavailable()

    return HTTPNoContent()
