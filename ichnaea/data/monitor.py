from collections import defaultdict
from datetime import timedelta

import markus

from ichnaea import util


METRICS = markus.get_metrics()


class ApiKeyLimits(object):
    def __init__(self, task):
        self.task = task

    def __call__(self):
        today = util.utcnow().strftime("%Y%m%d")
        keys = self.task.redis_client.keys("apilimit:*:" + today)
        values = []
        if keys:
            values = self.task.redis_client.mget(keys)
            keys = [k.decode("utf-8").split(":")[1:3] for k in keys]

        for (api_key, path), value in zip(keys, values):
            METRICS.gauge(
                "api.limit", value=int(value), tags=["key:" + api_key, "path:" + path]
            )


class ApiUsers(object):
    def __init__(self, task):
        self.task = task

    def __call__(self):
        days = {}
        today = util.utcnow().date()
        for i in range(0, 7):
            day = today - timedelta(days=i)
            days[i] = day.strftime("%Y-%m-%d")

        metrics = defaultdict(list)
        for key in self.task.redis_client.scan_iter(match="apiuser:*", count=100):
            _, api_type, api_name, day = key.decode("ascii").split(":")
            if day not in days.values():
                # delete older entries
                self.task.redis_client.delete(key)
                continue

            if day == days[0]:
                metrics[(api_type, api_name, "1d")].append(key)

            metrics[(api_type, api_name, "7d")].append(key)

        for parts, keys in metrics.items():
            api_type, api_name, interval = parts
            value = self.task.redis_client.pfcount(*keys)

            METRICS.gauge(
                "%s.user" % api_type,
                value=value,
                tags=["key:%s" % api_name, "interval:%s" % interval],
            )
