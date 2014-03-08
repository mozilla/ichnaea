import socket

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPServiceUnavailable
from sqlalchemy.sql import select
from sqlalchemy.sql import func

LOCAL_FQDN = socket.getfqdn()


def configure_heartbeat(config):
    config.scan('ichnaea.service.heartbeat.views')


@view_config(renderer='json', name="__heartbeat__")
def heartbeat_view(request):
    try:
        session = request.db_slave_session
        conn = session.connection()
        if conn.execute(select([func.now()])).first() is None:
            return HTTPServiceUnavailable()
        else:
            return {'status': 'OK', 'hostname': LOCAL_FQDN}
    except Exception:
        return HTTPServiceUnavailable()
