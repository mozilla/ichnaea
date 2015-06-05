import socket

from pyramid.httpexceptions import HTTPServiceUnavailable

from ichnaea.api.base import BaseServiceView

LOCAL_FQDN = socket.getfqdn()


class HeartbeatView(BaseServiceView):

    route = '/__heartbeat__'

    def __call__(self):
        try:
            return {'status': 'OK', 'hostname': LOCAL_FQDN}
        except Exception:  # pragma: no cover
            return HTTPServiceUnavailable()
