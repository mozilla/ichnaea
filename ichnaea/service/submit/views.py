from pyramid.httpexceptions import (
    HTTPNoContent,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.customjson import kombu_dumps
from ichnaea.data.tasks import insert_measures
from ichnaea.service.error import (
    JSONError,
    preprocess_request,
)
from ichnaea.service.submit.schema import SubmitSchema
from ichnaea.service.base import check_api_key


def configure_submit(config):
    config.add_route('v1_submit', '/v1/submit')
    config.add_view(submit_view, route_name='v1_submit', renderer='json')


def add_radio_value(data):
    radio = data.get('radio', None)
    cells = data.get('cell', ())

    for cell in cells:
        if cell['radio'] is None:
            cell['radio'] = radio

    data['cell'] = tuple(cells)


def submit_validator(data, errors):
    for item in data.get('items', ()):
        add_radio_value(item)


@check_api_key('submit', error_on_invalidkey=False)
def submit_view(request):
    stats_client = request.registry.stats_client
    api_key_log = getattr(request, 'api_key_log', False)
    api_key_name = getattr(request, 'api_key_name', None)

    try:
        data, errors = preprocess_request(
            request,
            schema=SubmitSchema(),
            extra_checks=(submit_validator, ),
            response=JSONError,
        )
    except JSONError:
        # capture JSON exceptions for submit calls
        request.registry.raven_client.captureException()
        raise

    items = data['items']
    nickname = request.headers.get('X-Nickname', u'')
    if isinstance(nickname, str):
        nickname = nickname.decode('utf-8', 'ignore')

    email = request.headers.get('X-Email', u'')
    if isinstance(email, str):
        email = email.decode('utf-8', 'ignore')

    # count the number of batches and emit a pseudo-timer to capture
    # the number of reports per batch
    length = len(items)
    stats_client.incr('items.uploaded.batches')
    stats_client.timing('items.uploaded.batch_size', length)

    if api_key_log:
        stats_client.incr(
            'items.api_log.%s.uploaded.batches' % api_key_name)
        stats_client.timing(
            'items.api_log.%s.uploaded.batch_size' % api_key_name, length)

    # batch incoming data into multiple tasks, in case someone
    # manages to submit us a huge single request
    for i in range(0, length, 100):
        batch = kombu_dumps(items[i:i + 100])
        # insert observations, expire the task if it wasn't processed
        # after six hours to avoid queue overload
        try:
            insert_measures.apply_async(
                kwargs={
                    'email': email,
                    'items': batch,
                    'nickname': nickname,
                    'api_key_log': api_key_log,
                    'api_key_name': api_key_name,
                },
                expires=21600)
        except ConnectionError:  # pragma: no cover
            return HTTPServiceUnavailable()

    return HTTPNoContent()
