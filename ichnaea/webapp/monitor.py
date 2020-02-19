"""
Heartbeat and monitor views to check service and backend health.
"""
import time

from pyramid.httpexceptions import HTTPServiceUnavailable

from ichnaea.db import ping_session
from ichnaea.util import contribute_info, version_info
from ichnaea.webapp.view import BaseView


def _check_timed(ping_function):
    start_time = time.time()
    success = ping_function()
    if not success:
        return {"up": False, "time": 0}
    delta = time.time() - start_time
    return {"up": True, "time": int(round(1000 * delta))}


def check_database(request):
    """Check that the database is available for a simple query."""
    data = _check_timed(lambda: ping_session(request.db_session))
    if data["up"]:
        current_heads = [
            row[0]
            for row in request.db_session.execute(
                "select version_num from alembic_version"
            )
        ]
        alembic_version = ",".join(sorted(current_heads))
    else:
        alembic_version = "unknown"
    data["alembic_version"] = alembic_version
    return data


def check_geoip(request):
    geoip_db = request.registry.geoip_db
    result = _check_timed(geoip_db.ping)
    result["age_in_days"] = geoip_db.age
    result["version"] = geoip_db.version
    return result


def check_redis(request):
    return _check_timed(request.registry.redis_client.ping)


def configure_monitor(config):
    """Configure monitor related views and set up routes."""
    ContributeView.configure(config)
    HeartbeatView.configure(config)
    LBHeartbeatView.configure(config)
    VersionView.configure(config)


class ContributeView(BaseView):
    """
    A view returning information about how to contribute to the project.
    """

    route = "/contribute.json"

    def __call__(self):
        """
        Return a response with a 200 status, including a JSON body
        describing how to contribute to the project.
        """
        return contribute_info()


class HeartbeatView(BaseView):
    """
    A heartbeat view which returns a successful response if the service
    and all its backend connections work.

    The view actively checks the database, geoip and redis connections.
    """

    route = "/__heartbeat__"

    def __call__(self):
        """
        Return a response with a 200 or 503 status, including
        a JSON body listing the status and timing information for
        most outbound connections.
        """
        services = {
            "database": check_database,
            "geoip": check_geoip,
            "redis": check_redis,
        }
        failed = False
        result = {}
        for name, check in services.items():
            try:
                service_result = check(self.request)
            except Exception:
                result[name] = {"up": None, "time": -1}
                failed = True
            else:
                result[name] = service_result
                if not service_result["up"]:
                    failed = True

        if failed:
            response = self.prepare_exception(HTTPServiceUnavailable())
            response.content_type = "application/json"
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

    route = "/__lbheartbeat__"

    def __call__(self):
        """Return a response with a 200 or 503 status."""
        try:
            return {"status": "OK"}
        except Exception:
            raise self.prepare_exception(HTTPServiceUnavailable())


class VersionView(BaseView):
    """
    A view which returns information about the running software version.
    """

    route = "/__version__"

    def __call__(self):
        """
        Return a response with a 200 status, including a JSON body
        describing the installed software versions.
        """
        return version_info()
