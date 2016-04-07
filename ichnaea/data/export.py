from collections import defaultdict
from contextlib import closing
from datetime import datetime
import re
import time
import uuid

import boto
import boto.exception
import redis.exceptions
import requests
import requests.exceptions
import pytz
import simplejson
from six.moves.urllib.parse import urlparse
import sqlalchemy.exc

from ichnaea.models import (
    ApiKey,
    BlueObservation,
    BlueReport,
    BlueShard,
    CellObservation,
    CellReport,
    CellShard,
    DataMap,
    Report,
    ScoreKey,
    User,
    WifiObservation,
    WifiReport,
    WifiShard,
)
from ichnaea.models.content import encode_datamap_grid
from ichnaea.queue import DataQueue
from ichnaea import util

WHITESPACE = re.compile('\s', flags=re.UNICODE)


class IncomingQueue(object):
    """
    The incoming queue contains the data collected in the web application
    tier. It is the single entrypoint from which all other data pipelines
    get their data.

    It distributes the data into the configured export queues.
    """

    def __init__(self, task):
        self.task = task

    def __call__(self):
        data_queue = self.task.app.data_queues['update_incoming']
        data = data_queue.dequeue()

        grouped = defaultdict(list)
        for item in data:
            grouped[item['api_key']].append({
                'api_key': item['api_key'],
                'nickname': item['nickname'],
                'report': item['report'],
            })

        export_queues = self.task.app.export_queues
        with self.task.redis_pipeline() as pipe:
            for api_key, items in grouped.items():
                for queue in export_queues.values():
                    if queue.export_allowed(api_key):
                        queue_key = queue.queue_key(api_key)
                        queue.enqueue(items, queue_key, pipe=pipe)

        if data_queue.ready():  # pragma: no cover
            self.task.apply_countdown()


class ExportScheduler(object):
    """
    The export scheduler is periodically called, checks all export queues
    and if they contain enough or old enough data schedules an async
    export task to process the data in the export queue.
    """

    def __init__(self, task):
        self.task = task

    def __call__(self, export_task):
        for export_queue in self.task.app.export_queues.values():
            for queue_key in export_queue.partitions():
                if export_queue.ready(queue_key):
                    export_task.delay(export_queue.name,
                                      queue_key=queue_key)


class ReportExporter(object):

    _retriable = (IOError, )
    _retries = 3
    _retry_wait = 1.0

    def __init__(self, task, export_queue_name, queue_key):
        self.task = task
        self.export_queue_name = export_queue_name
        self.export_queue = task.app.export_queues[export_queue_name]
        self.stats_tags = ['key:' + self.export_queue.metric_tag()]
        self.queue_key = queue_key
        if not self.queue_key:  # pragma: no cover
            # BBB
            self.queue_key = self.export_queue.queue_key(None)

    def __call__(self):
        items = self.export_queue.dequeue(self.queue_key)
        if not items:  # pragma: no cover
            return

        queue_items = items
        if not self.export_queue.metadata:
            # ignore metadata
            queue_items = {'items': [item['report'] for item in items]}

        success = False
        for i in range(self._retries):
            try:

                with self.task.stats_client.timed('data.export.upload',
                                                  tags=self.stats_tags):
                    self.send(queue_items)

                success = True
            except self._retriable:
                success = False
                time.sleep(self._retry_wait * (i ** 2 + 1))

            if success:
                self.task.stats_client.incr(
                    'data.export.batch', tags=self.stats_tags)
                break

        if success and self.export_queue.ready(self.queue_key):
            self.task.apply_countdown(
                args=[self.export_queue_name],
                kwargs={'queue_key': self.queue_key})

    def send_data(self, data):  # pragma: no cover
        # BBB
        queue_items = simplejson.loads(data)
        self.send(queue_items)

    def send(self, queue_items):
        raise NotImplementedError()


class DummyExporter(ReportExporter):

    def send(self, queue_items):
        pass


class GeosubmitExporter(ReportExporter):

    _retriable = (
        IOError,
        requests.exceptions.RequestException,
    )

    def send(self, queue_items):
        headers = {
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
            'User-Agent': 'ichnaea',
        }

        response = requests.post(
            self.export_queue.url,
            data=util.encode_gzip(simplejson.dumps(queue_items),
                                  compresslevel=5),
            headers=headers,
            timeout=60.0,
        )

        # log upload_status and trigger exception for bad responses
        # this causes the task to be re-tried
        self.task.stats_client.incr(
            'data.export.upload',
            tags=self.stats_tags + ['status:%s' % response.status_code])
        response.raise_for_status()


class S3Exporter(ReportExporter):

    _retriable = (
        IOError,
        boto.exception.BotoClientError,
        boto.exception.BotoServerError,
    )

    def send(self, queue_items):
        _, bucket, path = urlparse(self.export_queue.url)[:3]
        # s3 key names start without a leading slash
        path = path.lstrip('/')
        if not path.endswith('/'):
            path += '/'

        year, month, day = util.utcnow().timetuple()[:3]
        # strip away queue prefix again
        api_key = self.queue_key.split(':')[-1]

        key_name = path.format(
            api_key=api_key, year=year, month=month, day=day)
        key_name += uuid.uuid1().hex + '.json.gz'

        try:
            conn = boto.connect_s3()
            bucket = conn.get_bucket(bucket, validate=False)
            with closing(boto.s3.key.Key(bucket)) as key:
                key.key = key_name
                key.content_encoding = 'gzip'
                key.content_type = 'application/json'
                key.set_contents_from_string(
                    util.encode_gzip(simplejson.dumps(queue_items),
                                     compresslevel=7))

            self.task.stats_client.incr(
                'data.export.upload',
                tags=self.stats_tags + ['status:success'])
        except Exception:  # pragma: no cover
            self.task.stats_client.incr(
                'data.export.upload',
                tags=self.stats_tags + ['status:failure'])
            raise


class InternalTransform(object):
    """
    This maps the geosubmit v2 schema used in view code and external
    transfers (backup, forward to partners) to the internal submit v1
    schema used in our own database models.
    """

    # *_id maps a source section id to a target section id
    # *_map maps fields inside the section from source to target id
    # if the names are equal, a simple string can be specified instead
    # of a two-tuple

    position_id = ('position', None)
    position_map = [
        ('latitude', 'lat'),
        ('longitude', 'lon'),
        'accuracy',
        'altitude',
        ('altitudeAccuracy', 'altitude_accuracy'),
        'age',
        'heading',
        'pressure',
        'speed',
        'source',
    ]

    blue_id = ('bluetoothBeacons', 'blue')
    blue_map = [
        ('macAddress', 'mac'),
        'age',
        ('signalStrength', 'signal'),
    ]

    cell_id = ('cellTowers', 'cell')
    cell_map = [
        ('radioType', 'radio'),
        ('mobileCountryCode', 'mcc'),
        ('mobileNetworkCode', 'mnc'),
        ('locationAreaCode', 'lac'),
        ('cellId', 'cid'),
        'age',
        'asu',
        ('primaryScramblingCode', 'psc'),
        'serving',
        ('signalStrength', 'signal'),
        ('timingAdvance', 'ta'),
    ]

    wifi_id = ('wifiAccessPoints', 'wifi')
    wifi_map = [
        ('macAddress', 'mac'),
        ('radioType', 'radio'),
        'age',
        'channel',
        'frequency',
        'signalToNoiseRatio',
        ('signalStrength', 'signal'),
    ]

    def _map_dict(self, item_source, field_map):
        value = {}
        for spec in field_map:
            if isinstance(spec, tuple):
                source, target = spec
            else:
                source = spec
                target = spec
            source_value = item_source.get(source)
            if source_value is not None:
                value[target] = source_value
        return value

    def _parse_dict(self, item, report, key_map, field_map):
        value = {}
        item_source = item.get(key_map[0])
        if item_source:
            value = self._map_dict(item_source, field_map)
        if value:
            if key_map[1] is None:
                report.update(value)
            else:  # pragma: no cover
                report[key_map[1]] = value
        return value

    def _parse_list(self, item, report, key_map, field_map):
        values = []
        for value_item in item.get(key_map[0], ()):
            value = self._map_dict(value_item, field_map)
            if value:
                values.append(value)
        if values:
            report[key_map[1]] = values
        return values

    def __call__(self, item):
        report = {}
        self._parse_dict(item, report, self.position_id, self.position_map)

        timestamp = item.get('timestamp')
        if timestamp:
            report['timestamp'] = timestamp

        blues = self._parse_list(item, report, self.blue_id, self.blue_map)
        cells = self._parse_list(item, report, self.cell_id, self.cell_map)
        wifis = self._parse_list(item, report, self.wifi_id, self.wifi_map)

        if blues or cells or wifis:
            return report
        return {}


class InternalExporter(ReportExporter):

    _retriable = (
        IOError,
        redis.exceptions.RedisError,
        sqlalchemy.exc.InternalError,
    )
    transform = InternalTransform()

    def _format_report(self, item):
        report = self.transform(item)

        timestamp = report.pop('timestamp', None)
        if timestamp:
            dt = datetime.utcfromtimestamp(timestamp / 1000.0)
            report['time'] = dt.replace(microsecond=0, tzinfo=pytz.UTC)

        return report

    def send(self, queue_items):
        api_keys = set()
        api_keys_found = {}
        metrics = {}
        nicknames = set()
        scores = {}
        users = {}

        items = []
        for item in queue_items:
            # preprocess items and extract set of API keys and nicknames
            item['report'] = self._format_report(item['report'])
            if item['report']:
                items.append(item)
                api_keys.add(item['api_key'])
                nicknames.add(item['nickname'])

        for api_key in api_keys:
            metrics[api_key] = {}
            for type_ in ('report', 'blue', 'cell', 'wifi'):
                for action in ('drop', 'upload'):
                    metrics[api_key]['%s_%s' % (type_, action)] = 0

        with self.task.db_session() as session:
            # limit database session to get API keys and user ids
            for nickname in nicknames:
                userid = self.process_user(session, nickname)
                users[nickname] = userid
                scores[userid] = 0

            keys = [key for key in api_keys if key]
            if keys:
                query = (session.query(ApiKey.valid_key)
                                .filter(ApiKey.valid_key.in_(keys)))

                for row in query.all():
                    api_keys_found[row.valid_key] = True

        positions = []
        observations = {'blue': [], 'cell': [], 'wifi': []}

        for item in items:
            api_key = item['api_key']
            report = item['report']

            obs, malformed_obs = self.process_report(report)

            any_data = False
            for name in ('blue', 'cell', 'wifi'):
                if obs.get(name):
                    observations[name].extend(obs[name])
                    metrics[api_key][name + '_upload'] += len(obs[name])
                    any_data = True
                metrics[api_key][name + '_drop'] += malformed_obs.get(name, 0)

            metrics[api_key]['report_upload'] += 1
            if any_data:
                positions.append((report['lat'], report['lon']))
            else:
                metrics[api_key]['report_drop'] += 1

            userid = users.get(item['nickname'])
            if userid is not None:
                scores[userid] += 1

        for userid, score_value in scores.items():
            self.process_score(userid, score_value)

        with self.task.redis_pipeline() as pipe:
            self.queue_observations(pipe, observations)
            if positions:
                self.process_datamap(pipe, positions)

        self.emit_metrics(api_keys_found, metrics)

    def queue_observations(self, pipe, observations):
        for datatype, shard_model, shard_key, queue_prefix in (
                ('blue', BlueShard, 'mac', 'update_blue_'),
                ('cell', CellShard, 'cellid', 'update_cell_'),
                ('wifi', WifiShard, 'mac', 'update_wifi_')):

            queued_obs = defaultdict(list)
            for obs in observations[datatype]:
                # group by sharded queue
                shard_id = shard_model.shard_id(getattr(obs, shard_key))
                queue_id = queue_prefix + shard_id
                queued_obs[queue_id].append(obs.to_json())

            for queue_id, values in queued_obs.items():
                # enqueue values for each queue
                queue = self.task.app.data_queues[queue_id]
                queue.enqueue(values, pipe=pipe)

    def emit_metrics(self, api_keys_found, metrics):
        for api_key, key_metrics in metrics.items():
            api_tag = []
            if api_key and api_keys_found.get(api_key, False):
                api_tag = ['key:%s' % api_key]

            for name, count in key_metrics.items():
                if not count:
                    continue

                type_, action = name.split('_')
                if type_ == 'report':
                    suffix = 'report'
                    tags = api_tag
                else:
                    suffix = 'observation'
                    tags = ['type:%s' % type_] + api_tag

                self.task.stats_client.incr(
                    'data.%s.%s' % (suffix, action), count, tags=tags)

    def process_report(self, data):
        report = Report.create(**data)
        if report is None:
            return ({}, {})

        malformed = {}
        observations = {}
        for name, report_cls, obs_cls in (
                ('blue', BlueReport, BlueObservation),
                ('cell', CellReport, CellObservation),
                ('wifi', WifiReport, WifiObservation)):

            malformed[name] = 0
            observations[name] = {}

            if data.get(name):
                for item in data[name]:
                    # validate the blue/cell/wifi specific fields
                    item_report = report_cls.create(**item)
                    if item_report is None:
                        malformed[name] += 1
                        continue

                    # combine general and specific report data into one
                    item_obs = obs_cls.combine(report, item_report)
                    item_key = item_obs.unique_key

                    # if we have better data for the same key, ignore
                    existing = observations[name].get(item_key)
                    if existing is not None and existing.better(item_obs):
                        continue

                    observations[name][item_key] = item_obs

        obs = {
            'blue': observations['blue'].values(),
            'cell': observations['cell'].values(),
            'wifi': observations['wifi'].values(),
        }
        return (obs, malformed)

    def process_datamap(self, pipe, positions):
        grids = set()
        for lat, lon in positions:
            if lat is not None and lon is not None:
                grids.add(DataMap.scale(lat, lon))

        shards = defaultdict(set)
        for lat, lon in grids:
            shards[DataMap.shard_id(lat, lon)].add(
                encode_datamap_grid(lat, lon))

        for shard_id, values in shards.items():
            queue = self.task.app.data_queues['update_datamap_' + shard_id]
            queue.enqueue(list(values), pipe=pipe)

    def process_score(self, userid, pos_count):
        if userid is None or pos_count <= 0:
            return

        scores = [{
            'key': int(ScoreKey.location),
            'userid': userid,
            'value': pos_count,
        }]

        queue = self.task.app.data_queues['update_score']
        queue.enqueue(scores)

    def process_user(self, session, nickname):
        userid = None
        if nickname and (2 <= len(nickname) <= 128):
            # automatically create user objects and update nickname
            rows = session.query(User).filter(User.nickname == nickname)
            old = rows.first()
            if not old:
                user = User(
                    nickname=nickname,
                )
                session.add(user)
                session.flush()
                userid = user.id
            else:  # pragma: no cover
                userid = old.id

        return userid


class ExportQueue(object):
    """
    A Redis based queue which stores binary or JSON encoded items
    in lists. The queue supports dynamic queue keys and partitioned
    queues with a common queue key prefix.

    The lists maintain a TTL value corresponding to the time data has
    been last put into the queue.
    """

    exporter_type = None
    metadata = False

    def __init__(self, name, redis_client,
                 url=None, batch=0, skip_keys=(), compress=False):
        self.name = name
        self.redis_client = redis_client
        self.batch = batch
        self.url = url
        self.skip_keys = skip_keys
        self.compress = compress

    def _data_queue(self, queue_key):
        return DataQueue(queue_key, self.redis_client,
                         batch=self.batch, compress=self.compress, json=True)

    @classmethod
    def configure_queue(cls, key, redis_client, settings, compress=False):
        url = settings.get('url', '') or ''
        scheme = urlparse(url).scheme
        batch = int(settings.get('batch', 0))

        skip_keys = WHITESPACE.split(settings.get('skip_keys', ''))
        skip_keys = tuple([skip_key for skip_key in skip_keys if skip_key])

        queue_types = {
            'dummy': DummyExportQueue,
            'http': HTTPSExportQueue,
            'https': HTTPSExportQueue,
            'internal': InternalExportQueue,
            's3': S3ExportQueue,
        }
        klass = queue_types.get(scheme, cls)

        return klass(key, redis_client,
                     url=url, batch=batch, skip_keys=skip_keys,
                     compress=compress)

    def dequeue(self, queue_key):
        return self._data_queue(queue_key).dequeue()

    def enqueue(self, items, queue_key, pipe=None):
        self._data_queue(queue_key).enqueue(items, pipe=pipe)

    def export(self, task, queue_key):
        if self.exporter_type is not None:
            self.exporter_type(task, self.name, queue_key)()

    def export_allowed(self, api_key):
        return (api_key not in self.skip_keys)

    def metric_tag(self):
        # strip away queue_export_ prefix
        return self.name[13:]

    def partitions(self):
        return [self.name]

    def queue_key(self, api_key):
        return self.name

    def ready(self, queue_key):
        if queue_key is None:  # pragma: no cover
            # BBB
            queue_key = self.name
        return self._data_queue(queue_key).ready()


class DummyExportQueue(ExportQueue):

    exporter_type = DummyExporter


class HTTPSExportQueue(ExportQueue):

    exporter_type = GeosubmitExporter


class InternalExportQueue(ExportQueue):

    exporter_type = InternalExporter
    metadata = True


class S3ExportQueue(ExportQueue):

    exporter_type = S3Exporter

    def partitions(self):
        # e.g. ['queue_export_something:api_key']
        return self.redis_client.scan_iter(match=self.name + ':*', count=100)

    def queue_key(self, api_key=None):
        if not api_key:
            api_key = 'no_key'
        return self.name + ':' + api_key
