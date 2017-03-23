"""
Heartbeat and monitor views to check service and backend health.
"""
import time

from pyramid.httpexceptions import HTTPServiceUnavailable

from ichnaea.config import (
    CONTRIBUTE_INFO,
    VERSION_INFO,
)
from ichnaea.webapp.view import BaseView


def _check_timed(ping_function):
    with Timer() as timer:
        success = ping_function()
    if not success:
        return {'up': False, 'time': 0}
    return {'up': True, 'time': timer.ms}


def check_database(request):
    return _check_timed(request.db_session.ping)


def check_geoip(request):
    geoip_db = request.registry.geoip_db
    result = _check_timed(geoip_db.ping)
    result['age_in_days'] = geoip_db.age
    return result


def check_redis(request):
    return _check_timed(request.registry.redis_client.ping)


def configure_monitor(config):
    """Configure monitor related views and set up routes."""
    ContributeView.configure(config)
    HeartbeatView.configure(config)
    LBHeartbeatView.configure(config)
    VersionView.configure(config)


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


class ContributeView(BaseView):
    """
    A view returning information about how to contribute to the project.
    """

    route = '/contribute.json'

    def __call__(self):
        """
        Return a response with a 200 status, including a JSON body
        describing how to contribute to the project.
        """
        return CONTRIBUTE_INFO


class HeartbeatView(BaseView):
    """
    A heartbeat view which returns a successful response if the service
    and all its backend connections work.

    The view actively checks the database, geoip and redis connections.
    """

    route = '/__heartbeat__'

    def __call__(self):
        """
        Return a response with a 200 or 503 status, including
        a JSON body listing the status and timing information for
        most outbound connections.
        """
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
            response = self.prepare_exception(HTTPServiceUnavailable())
            response.content_type = 'application/json'
            response.json = result
            return response

        return result


class LBHeartbeatView(BaseView):
    """
    A loadbalancer heartbeat view which returns a successful response if
    the service is reachable and works at all. If any of the backend
    connections are broken, this view will still respond with a success,
    allowing the service to operate in a degraded mode.

    This view is typically used in load balancer health checks.
    """

    route = '/__lbheartbeat__'

    def __call__(self):
        """Return a response with a 200 or 503 status."""
        try:
            return {'status': 'OK'}
        except Exception:  # pragma: no cover
            raise self.prepare_exception(HTTPServiceUnavailable())


class VersionView(BaseView):
    """
    A view which returns information about the running software version.
    """

    route = '/__version__'

    def __call__(self):
        """
        Return a response with a 200 status, including a JSON body
        describing the installed software versions.
        """
        return VERSION_INFO
