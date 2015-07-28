from ichnaea.api.exceptions import UploadSuccessV1
from ichnaea.api.submit.submit_v1.schema import SubmitV1Schema
from ichnaea.api.submit.views import BaseSubmitView


class SubmitV1View(BaseSubmitView):

    metric_path = 'v1.submit'  #:
    route = '/v1/submit'  #:
    schema = SubmitV1Schema  #:

    #: :exc:`ichnaea.api.exceptions.UploadSuccessV1`
    success = UploadSuccessV1
