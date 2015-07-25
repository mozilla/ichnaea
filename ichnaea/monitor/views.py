import socket
import time

from pyramid.httpexceptions import HTTPServiceUnavailable

from ichnaea.webapp.view import BaseView

LOCAL_FQDN = socket.getfqdn()


class Timer(object):

    def __init__(self):
        self.start = None
        self.ms = None

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, typ, value, tb):
        if self.start is not None:
            dt = time.time() - self.start
            self.ms = int(round(1000 * dt))


def _check_timed(ping_function):
    with Timer() as timer:
        success = ping_function()
    if not success:
        return {'up': False, 'time': 0}
    return {'up': True, 'time': timer.ms}


def check_database(request):
    return _check_timed(request.db_ro_session.ping)


def check_geoip(request):
    geoip_db = request.registry.geoip_db
    result = _check_timed(geoip_db.ping)
    result['age_in_days'] = geoip_db.age
    return result


def check_redis(request):
    return _check_timed(request.registry.redis_client.ping)


class HeartbeatView(BaseView):

    route = '/__heartbeat__'

    def __call__(self):
        try:
            return {'status': 'OK', 'hostname': LOCAL_FQDN}
        except Exception:  # pragma: no cover
            raise HTTPServiceUnavailable()


class MonitorView(BaseView):

    route = '/__monitor__'

    def __call__(self):
        services = {
            'database': check_database,
            'geoip': check_geoip,
            'redis': check_redis,
        }
        failed = False
        result = {}
        for name, check in services.items():
            try:
                service_result = check(self.request)
            except Exception:  # pragma: no cover
                result[name] = {'up': None, 'time': -1}
                failed = True
            else:
                result[name] = service_result
                if not service_result['up']:
                    failed = True

        if failed:
            response = HTTPServiceUnavailable()
            response.content_type = 'application/json'
            response.json = result
            return response

        return result
