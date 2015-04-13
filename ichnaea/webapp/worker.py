import gevent
from gunicorn.workers.ggevent import GeventWorker


class LocationGeventWorker(GeventWorker):
    """
    Custom gunicorn worker with extra operational niceties.

    This is a custom gunicorn worker class, based on the standard gevent worker
    but with some extra operational- and debugging-related features:

    * a timeout enforced on each individual request, rather than on
      inactivity of the worker as a whole.
    """

    def handle_request(self, *args):
        # Apply the configured 'timeout' value to each individual request.
        # Note that self.timeout is set to half the configured timeout by
        # the arbiter, so we use the value directly from the config.
        with gevent.Timeout(self.cfg.timeout):
            return super(LocationGeventWorker, self).handle_request(*args)
