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
    # TODO manually convert items to json with support for decimal/datetime
    items = dumps(request.validated['items'])
    insert_measures.delay(
        items=items,
        nickname=request.headers.get('X-Nickname', ''),
    )
    return HTTPNoContent()
