"""
Implementation of transfer specific HTTP service views.
"""

from redis import RedisError

from ichnaea.api.exceptions import (
    ParseError,
    ServiceUnavailable,
    TransferSuccess,
)
from ichnaea.api.views import BaseAPIView
from ichnaea.api.transfer.schema import TRANSFER_V1_SCHEMA


class BaseTransferView(BaseAPIView):
    """Common base class for all transfer related views."""

    check_api_key = True
    error_on_invalidkey = True  #:
    view_type = 'transfer'  #:

    #: :exc:`ichnaea.api.exceptions.TransferSuccess`
    success = TransferSuccess

    def __init__(self, request):
        super(BaseTransferView, self).__init__(request)
        self.queue = self.request.registry.data_queues['transfer_incoming']

    def transfer(self, api_key):
        # may raise HTTP error
        request_data, errors = self.preprocess_request()

        if not request_data:
            # don't allow completely empty request
            raise self.prepare_exception(ParseError())

        valid_key = api_key.valid_key
        data = []
        for item in request_data['items']:  # pragma: no cover
            # TODO
            data.append({
                'api_key': valid_key,
                'item': item,
            })

        self.queue.enqueue(data)

    def view(self, api_key):
        """
        Execute the view code and return a response.
        """
        try:
            self.transfer(api_key)
        except RedisError:
            raise self.prepare_exception(ServiceUnavailable())

        return self.prepare_exception(self.success())


class TransferV1View(BaseTransferView):
    """"Transfer version 1 view for `/v1/transfer`."""

    metric_path = 'v1.transfer'  #:
    route = '/v1/transfer'  #:
    schema = TRANSFER_V1_SCHEMA  #:
