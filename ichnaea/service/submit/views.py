from pyramid.httpexceptions import HTTPNoContent

from ichnaea.decimaljson import dumps
from ichnaea.heka_logging import get_heka_client
from ichnaea.models import (
    ApiKey
)
from ichnaea.service.error import (
    preprocess_request,
)
from ichnaea.service.submit.schema import SubmitSchema
from ichnaea.service.submit.tasks import insert_measures


def configure_submit(config):
    config.add_route('v1_submit', '/v1/submit')
    config.add_view(submit_view, route_name='v1_submit', renderer='json')


def check_cell_or_wifi(data, errors):
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi) and not any(cell):
        return False
    return True


def submit_validator(data, errors):
    # for each of the measurements, if the lat or lon is -255
    # drop the node
    skips = set()
    for idx, item in enumerate(data.get('items', ())):
        if item['lat'] == -255 or item['lon'] == -255:
            skips.add(idx)

        if not check_cell_or_wifi(item, errors):
            skips.add(idx)

    skips = list(skips)
    skips.sort(reverse=True)
    for idx in skips:
        del data['items'][idx]

    if errors:
        # don't add this error if something else was already wrong
        return


def submit_view(request):
    api_key = request.GET.get('key', None)
    heka_client = get_heka_client()

    if api_key is None:
        # we don't require API keys for submit yet
        heka_client.incr('submit.no_api_key')
    else:
        session = request.db_slave_session
        found_key_filter = session.query(ApiKey)
        found_key_filter = found_key_filter.filter(ApiKey.valid_key == api_key)
        if found_key_filter.count():
            heka_client.incr('submit.api_key.%s' % api_key.replace('.', '__'))
        else:
            heka_client.incr('submit.unknown_api_key')

    data, errors = preprocess_request(
        request,
        schema=SubmitSchema(),
        extra_checks=(submit_validator, ),
    )

    items = data['items']
    nickname = request.headers.get('X-Nickname', u'')
    if isinstance(nickname, str):
        nickname = nickname.decode('utf-8', 'ignore')
    # batch incoming data into multiple tasks, in case someone
    # manages to submit us a huge single request
    for i in range(0, len(items), 100):
        insert_measures.delay(
            # TODO convert items to json with support for decimal/datetime
            items=dumps(items[i:i + 100]),
            nickname=nickname,
        )
    return HTTPNoContent()
