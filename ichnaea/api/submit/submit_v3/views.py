from ichnaea.api.submit.submit_v3.schema import SubmitV3Schema
from ichnaea.api.submit.views import BaseSubmitView


class SubmitV3View(BaseSubmitView):

    metric_path = 'v2.geosubmit'  #:
    route = '/v2/geosubmit'  #:
    schema = SubmitV3Schema  #:
