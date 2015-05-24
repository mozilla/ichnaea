import socket

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPServiceUnavailable

LOCAL_FQDN = socket.getfqdn()


def configure_heartbeat(config):
    config.scan('ichnaea.service.heartbeat.views')


@view_config(renderer='json', name='__heartbeat__')
def heartbeat_view(request):
    try:
        return {'status': 'OK', 'hostname': LOCAL_FQDN}
    except Exception:  # pragma: no cover
        return HTTPServiceUnavailable()
