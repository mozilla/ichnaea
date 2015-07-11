"""
Implementation of a submit specific HTTP service view.
"""

from pyramid.httpexceptions import (
    HTTPOk,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.api.exceptions import ParseError
from ichnaea.api.views import BaseAPIView
from ichnaea.data.tasks import queue_reports


class BaseSubmitView(BaseAPIView):

    error_on_invalidkey = False  #:
    transform = None  #:
    schema = None  #:
    view_name = None  #:

    def __init__(self, request):
        super(BaseSubmitView, self).__init__(request)
        self.email, self.nickname = self.get_request_user_data()

    def decode_request_header(self, header_name):
        value = self.request.headers.get(header_name, None)
        if isinstance(value, str):  # pragma: no cover
            value = value.decode('utf-8', 'ignore')
        return value

    def get_request_user_data(self):
        email = self.decode_request_header('X-Email')
        nickname = self.decode_request_header('X-Nickname')
        return (email, nickname)

    def emit_upload_metrics(self, value, api_key):
        # count the number of batches and emit a pseudo-timer to capture
        # the number of reports per batch
        self.stats_client.incr('items.uploaded.batches')
        self.stats_client.timing('items.uploaded.batch_size', value)

        if api_key.log:
            api_key_name = api_key.name
            self.stats_client.incr(
                'items.api_log.%s.uploaded.batches' % api_key_name)
            self.stats_client.timing(
                'items.api_log.%s.uploaded.batch_size' % api_key_name, value)

    def preprocess(self, api_key):
        try:
            request_data, errors = self.preprocess_request()

            if not request_data:
                # don't allow completely empty submit request
                raise ParseError()

        except ParseError:
            # capture JSON exceptions for submit calls
            self.raven_client.captureException()
            raise

        self.emit_upload_metrics(len(request_data['items']), api_key)
        return request_data

    def submit(self, api_key):
        # may raise HTTP error
        request_data = self.preprocess(api_key)

        # data pipeline using new internal data format
        transform = self.transform()
        reports = transform.transform_many(request_data['items'])
        for i in range(0, len(reports), 100):
            batch = reports[i:i + 100]
            # insert reports, expire the task if it wasn't processed
            # after six hours to avoid queue overload
            queue_reports.apply_async(
                kwargs={
                    'api_key': api_key.valid_key,
                    'email': self.email,
                    'ip': self.request.client_addr,
                    'nickname': self.nickname,
                    'reports': batch,
                },
                expires=21600)

    def success(self):
        response = HTTPOk()
        response.content_type = 'application/json'
        response.body = b'{}'
        return response

    def view(self, api_key):
        """
        Execute the view code and return a response.
        """
        try:
            self.submit(api_key)
        except ConnectionError:  # pragma: no cover
            return HTTPServiceUnavailable()

        return self.success()
