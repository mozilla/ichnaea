from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import load_only

from ichnaea.models import (
    ApiKey,
    OCIDCell,
)
from ichnaea import util


class ApiKeyLimits(object):

    def __init__(self, task, session):
        self.task = task
        self.session = session
        self.redis_client = task.redis_client
        self.stats_client = task.stats_client

    def __call__(self):
        today = util.utcnow().strftime('%Y%m%d')
        keys = self.redis_client.keys('apilimit:*:' + today)
        if keys:
            values = self.redis_client.mget(keys)
            keys = [k.decode('utf-8').split(':')[1] for k in keys]
        else:
            values = []

        names = {}
        if keys:
            query = (self.session.query(ApiKey)
                                 .filter(ApiKey.valid_key.in_(keys))
                                 .options(load_only('shortname')))
            for api_key in query.all():
                names[api_key.valid_key] = api_key.name

        result = {}
        for k, v in zip(keys, values):
            name = names.get(k, k)
            value = int(v)
            result[name] = value
            self.stats_client.gauge(
                'api.limit', value, tags=['key:' + name])
        return result


class ApiUsers(object):

    def __init__(self, task):
        self.task = task
        self.redis_client = task.redis_client
        self.stats_client = task.stats_client

    def __call__(self):
        days = {}
        today = util.utcnow().date()
        for i in range(0, 7):
            day = today - timedelta(days=i)
            days[i] = day.strftime('%Y-%m-%d')

        metrics = defaultdict(list)
        result = {}
        for key in self.redis_client.scan_iter(
                match='apiuser:*', count=100):
            _, api_type, api_name, day = key.decode('ascii').split(':')
            if day not in days.values():
                # delete older entries
                self.redis_client.delete(key)
                continue

            if day == days[0]:
                metrics[(api_type, api_name, '1d')].append(key)

            metrics[(api_type, api_name, '7d')].append(key)

        for parts, keys in metrics.items():
            api_type, api_name, interval = parts
            value = self.redis_client.pfcount(*keys)

            self.stats_client.gauge(
                '%s.user' % api_type, value,
                tags=['key:%s' % api_name, 'interval:%s' % interval])
            result['%s:%s:%s' % parts] = value
        return result


class OcidImport(object):

    def __init__(self, task, session):
        self.task = task
        self.session = session
        self.stats_client = task.stats_client

    def __call__(self):
        result = -1
        now = util.utcnow()
        query = self.session.query(func.max(OCIDCell.created))
        max_created = query.first()[0]
        if max_created:
            # diff between now and the value, in milliseconds
            diff = now - max_created
            result = (diff.days * 86400 + diff.seconds) * 1000

        self.stats_client.gauge('table', result, tags=['table:ocid_cell_age'])
        return result


class QueueSize(object):

    def __init__(self, task):
        self.task = task
        self.redis_client = task.redis_client
        self.stats_client = task.stats_client

    def __call__(self):
        result = {}
        for name in self.task.app.all_queues:
            result[name] = value = self.redis_client.llen(name)
            self.stats_client.gauge('queue', value, tags=['queue:' + name])
        return result
