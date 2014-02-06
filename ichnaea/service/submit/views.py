from cornice import Service
from pyramid.httpexceptions import HTTPNoContent

from ichnaea.decimaljson import dumps
from ichnaea.service.error import (
    error_handler,
    MSG_ONE_OF,
)
from ichnaea.service.submit.schema import SubmitSchema
from ichnaea.service.submit.tasks import insert_measures


def configure_submit(config):
    config.scan('ichnaea.service.submit.views')


def check_cell_or_wifi(data, request):
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi) and not any(cell):
        request.errors.add('body', 'body', MSG_ONE_OF)


def submit_validator(request):
    if len(request.errors):
        return
    for item in request.validated['items']:
        if not check_cell_or_wifi(item, request):
            # quit on first Error
            return


submit = Service(
    name='submit',
    path='/v1/submit',
    description="Submit a measurement result for a location.",
)


@submit.post(renderer='json', accept="application/json",
             schema=SubmitSchema, error_handler=error_handler,
             validators=submit_validator)
def submit_post(request):
    items = request.validated['items']
    nickname = request.headers.get('X-Nickname', '')
    # batch incoming data into multiple tasks, in case someone
    # manages to submit us a huge single request
    for i in range(0, len(items), 100):
        insert_measures.delay(
            # TODO convert items to json with support for decimal/datetime
            items=dumps(items[i:i + 100]),
            nickname=nickname,
        )
    return HTTPNoContent()
