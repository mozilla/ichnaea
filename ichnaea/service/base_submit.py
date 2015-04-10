from ichnaea.customjson import kombu_dumps
from ichnaea.data.tasks import (
    insert_measures,
    queue_reports,
)
from ichnaea.service.error import preprocess_request


class BaseSubmitter(object):

    schema = None
    error_response = None

    def __init__(self, request):
        self.request = request
        self.raven_client = request.registry.raven_client
        self.stats_client = request.registry.stats_client
        self.api_key = request.GET.get('key', None)
        self.api_key_log = getattr(request, 'api_key_log', False)
        self.api_key_name = getattr(request, 'api_key_name', None)
        self.email, self.nickname = self.get_request_user_data()

    def decode_request_header(self, header_name):
        value = self.request.headers.get(header_name, u'')
        if isinstance(value, str):
            value = value.decode('utf-8', 'ignore')
        return value

    def get_request_user_data(self):
        email = self.decode_request_header('X-Email')
        nickname = self.decode_request_header('X-Nickname')
        return (email, nickname)

    def emit_upload_metrics(self, value):
        # count the number of batches and emit a pseudo-timer to capture
        # the number of reports per batch
        self.stats_client.incr('items.uploaded.batches')
        self.stats_client.timing('items.uploaded.batch_size', value)

        if self.api_key_log:
            api_key_name = self.api_key_name
            self.stats_client.incr(
                'items.api_log.%s.uploaded.batches' % api_key_name)
            self.stats_client.timing(
                'items.api_log.%s.uploaded.batch_size' % api_key_name, value)

    def preprocess(self):
        try:
            request_data, errors = preprocess_request(
                self.request,
                schema=self.schema(),
                response=self.error_response,
            )
        except self.error_response:
            # capture JSON exceptions for submit calls
            self.raven_client.captureException()
            raise

        self.emit_upload_metrics(len(request_data['items']))
        return request_data

    def prepare_measure_data(self, request_data):  # pragma: no cover
        raise NotImplementedError()

    def insert_measures(self, request_data):
        # batch incoming data into multiple tasks, in case someone
        # manages to submit us a huge single request
        submit_data = self.prepare_measure_data(request_data)
        for i in range(0, len(submit_data), 100):
            batch = kombu_dumps(submit_data[i:i + 100])
            # insert observations, expire the task if it wasn't processed
            # after six hours to avoid queue overload
            insert_measures.apply_async(
                kwargs={
                    'email': self.email,
                    'items': batch,
                    'nickname': self.nickname,
                    'api_key_log': self.api_key_log,
                    'api_key_name': self.api_key_name,
                },
                expires=21600)

    def prepare_reports(self, request_data):  # pragma: no cover
        raise NotImplementedError()

    def submit(self, request_data):
        # secondary data pipeline using new internal data format
        reports = self.prepare_reports(request_data)
        for i in range(0, len(reports), 100):
            batch = reports[i:i + 100]
            # insert reports, expire the task if it wasn't processed
            # after six hours to avoid queue overload
            queue_reports.apply_async(
                kwargs={
                    'reports': batch,
                    'api_key': self.api_key,
                    'email': self.email,
                    'nickname': self.nickname,
                },
                expires=21600)
