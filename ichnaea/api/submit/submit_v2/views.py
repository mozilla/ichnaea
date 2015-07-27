from ichnaea.api.submit.submit_v2.schema import SubmitV2Schema
from ichnaea.api.submit.views import BaseSubmitView


class SubmitV2View(BaseSubmitView):

    route = '/v1/geosubmit'
    schema = SubmitV2Schema
    view_name = 'geosubmit'
