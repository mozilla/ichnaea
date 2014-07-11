from collections import deque

from statsd.client import StatsClient


STATS_CLIENT = None


def get_stats_client():
    return STATS_CLIENT


def set_stats_client(client):
    global STATS_CLIENT
    STATS_CLIENT = client
    return STATS_CLIENT


def configure_stats(config, _client=None):
    if _client is not None:
        return set_stats_client(_client)

    if not config:
        config = 'localhost:8125'
    parts = config.split(':')
    host = parts[0]
    port = 8125
    if len(parts) > 1:
        port = int(parts[1])

    client = StatsClient(host=host, port=port)
    return set_stats_client(client)


class DebugStatsClient(StatsClient):

    def __init__(self, host='localhost', port=8125, prefix=None,
                 maxudpsize=512):
        self._host = host
        self._port = port
        self._addr = None
        self._sock = None
        self._prefix = prefix
        self._maxudpsize = maxudpsize
        self.msgs = deque(maxlen=100)

    def _send(self, data):
        self.msgs.append(data)
