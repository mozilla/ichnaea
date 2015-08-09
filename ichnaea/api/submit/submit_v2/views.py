from ichnaea.api.submit.submit_v2.schema import SUBMIT_V2_SCHEMA
from ichnaea.api.submit.views import BaseSubmitView


class SubmitV2View(BaseSubmitView):

    metric_path = 'v1.geosubmit'  #:
    route = '/v1/geosubmit'  #:
    schema = SUBMIT_V2_SCHEMA  #:
