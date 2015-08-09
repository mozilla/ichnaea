from ichnaea.api.submit.submit_v3.schema import SUBMIT_V3_SCHEMA
from ichnaea.api.submit.views import BaseSubmitView


class SubmitV3View(BaseSubmitView):

    metric_path = 'v2.geosubmit'  #:
    route = '/v2/geosubmit'  #:
    schema = SUBMIT_V3_SCHEMA  #:
