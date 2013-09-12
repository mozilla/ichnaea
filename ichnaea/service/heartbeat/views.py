import socket

from pyramid.view import view_config

LOCAL_FQDN = socket.getfqdn()


def configure_heartbeat(config):
    config.scan('ichnaea.service.heartbeat.views')


@view_config(renderer='json', name="__heartbeat__")
def heartbeat_view(request):
    return {'status': 'OK', 'hostname': LOCAL_FQDN}
