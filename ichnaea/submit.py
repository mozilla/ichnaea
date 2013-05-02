from pyramid.httpexceptions import HTTPNoContent

from ichnaea.worker import add_measures


def submit_request(request):
    add_measures(request)
    return HTTPNoContent()
