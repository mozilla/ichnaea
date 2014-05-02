from pyramid.httpexceptions import HTTPNoContent

from ichnaea.decimaljson import dumps
from ichnaea.service.error import (
    preprocess_request,
)
from ichnaea.service.submit.schema import SubmitSchema
from ichnaea.service.submit.tasks import insert_measures
from ichnaea.service.base import check_api_key


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


@check_api_key('submit')
def submit_view(request):
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
