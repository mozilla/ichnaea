from collections import defaultdict
from datetime import datetime

import pytz
import simplejson

from ichnaea.data.upload import BaseReportUploader
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
    Score,
    ScoreKey,
    User,
    WifiObservation,
    WifiReport,
    WifiShard,
)
from ichnaea.models.content import encode_datamap_grid


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
        ('macAddress', 'key'),
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
        ('macAddress', 'key'),
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


class InternalUploader(BaseReportUploader):

    transform = InternalTransform()

    def __init__(self, task, pipe, export_queue_name, queue_key):
        super(InternalUploader, self).__init__(
            task, pipe, export_queue_name, queue_key)
        self.data_queues = self.task.app.data_queues

    def _format_report(self, item):
        report = self.transform(item)

        timestamp = report.pop('timestamp', None)
        if timestamp:
            dt = datetime.utcfromtimestamp(timestamp / 1000.0)
            report['time'] = dt.replace(microsecond=0, tzinfo=pytz.UTC)

        return report

    def send(self, url, data):
        with self.task.db_session() as session:
            self._send(session, url, data)

    def _send(self, session, url, data):
        groups = defaultdict(list)
        api_keys = set()
        nicknames = set()

        for item in simplejson.loads(data):
            report = self._format_report(item['report'])
            if report:
                groups[(item['api_key'], item['nickname'])].append(report)
                api_keys.add(item['api_key'])
                nicknames.add(item['nickname'])

        scores = {}
        users = {}
        for nickname in nicknames:
            userid = self.process_user(session, nickname)
            users[nickname] = userid
            scores[userid] = {
                'positions': 0,
                'new_stations': {
                    'blue': 0, 'cell': 0, 'wifi': 0
                },
            }

        metrics = {}
        for api_key in api_keys:
            metrics[api_key] = {
                'reports': 0,
                'malformed_reports': 0,
                'obs_count': {
                    'blue': {'upload': 0, 'drop': 0},
                    'cell': {'upload': 0, 'drop': 0},
                    'wifi': {'upload': 0, 'drop': 0},
                }
            }

        all_positions = []
        all_queued_obs = {
            'blue': defaultdict(list),
            'cell': defaultdict(list),
            'wifi': defaultdict(list),
        }

        for (api_key, nickname), reports in groups.items():
            userid = users.get(nickname)

            obs_queue, malformed_reports, obs_count, positions, \
                new_station_count = self.process_reports(
                    session, reports, userid)

            all_positions.extend(positions)
            for datatype, queued_obs in obs_queue.items():
                for queue_id, values in queued_obs.items():
                    all_queued_obs[datatype][queue_id].extend(values)

            metrics[api_key]['reports'] += len(reports)
            metrics[api_key]['malformed_reports'] += malformed_reports
            for datatype, type_stats in obs_count.items():
                for reason, value in type_stats.items():
                    metrics[api_key]['obs_count'][datatype][reason] += value

            if userid is not None:
                scores[userid]['positions'] += len(positions)
                for datatype, value in new_station_count.items():
                    scores[userid]['new_stations'][datatype] += value

        for userid, values in scores.items():
            self.process_score(
                userid, values['positions'], values['new_stations'])

        for datatype, queued_obs in all_queued_obs.items():
            for queue_id, values in queued_obs.items():
                queue = self.data_queues[queue_id]
                queue.enqueue(values, pipe=self.pipe)

        if all_positions:
            self.process_datamap(all_positions)

        for api_key, values in metrics.items():
            self.emit_stats(
                session,
                values['reports'],
                values['malformed_reports'],
                values['obs_count'],
                api_key=api_key,
            )

    def emit_stats(self, session, reports, malformed_reports, obs_count,
                   api_key=None):
        api_tag = []
        if api_key is not None:
            api_key = session.query(ApiKey).get(api_key)

        if api_key and api_key.should_log('submit'):
            api_tag = ['key:%s' % api_key.valid_key]

        if reports > 0:
            self.task.stats_client.incr(
                'data.report.upload', reports, tags=api_tag)

        if malformed_reports > 0:
            self.task.stats_client.incr(
                'data.report.drop', malformed_reports,
                tags=['reason:malformed'] + api_tag)

        for name, stats in obs_count.items():
            for action, count in stats.items():
                if count > 0:
                    tags = ['type:%s' % name]
                    if action == 'drop':
                        tags.append('reason:malformed')
                    self.task.stats_client.incr(
                        'data.observation.%s' % action,
                        count,
                        tags=tags + api_tag)

    def new_stations(self, session, shard_key, observations):
        # observations are pre-grouped per shard
        shard = observations[0].shard_model
        key_column = getattr(shard, shard_key)

        keys = set([obs.unique_key for obs in observations])
        query = (session.query(key_column)
                        .filter(key_column.in_(keys)))
        return len(keys) - query.count()

    def process_reports(self, session, reports, userid):
        malformed_reports = 0
        positions = set()
        observations = {}
        obs_count = {}
        obs_queue = {}
        new_station_count = {}

        for name in ('blue', 'cell', 'wifi'):
            observations[name] = []
            obs_count[name] = {'upload': 0, 'drop': 0}
            obs_queue[name] = defaultdict(list)
            new_station_count[name] = 0

        for report in reports:
            obs, malformed_obs = self.process_report(report)

            any_data = False
            for name in ('blue', 'cell', 'wifi'):
                if obs.get(name):
                    observations[name].extend(obs[name])
                    obs_count[name]['upload'] += len(obs[name])
                    any_data = True
                obs_count[name]['drop'] += malformed_obs.get(name, 0)

            if any_data:
                positions.add((report['lat'], report['lon']))
            else:
                malformed_reports += 1

        for name, shard_model, shard_key, queue_prefix in (
                ('blue', BlueShard, 'mac', 'update_blue_'),
                ('cell', CellShard, 'cellid', 'update_cell_'),
                ('wifi', WifiShard, 'mac', 'update_wifi_')):

            if observations[name]:
                sharded_obs = defaultdict(list)
                for ob in observations[name]:
                    shard_id = shard_model.shard_id(getattr(ob, shard_key))
                    sharded_obs[shard_id].append(ob)

                for shard_id, values in sharded_obs.items():
                    obs_queue[name][queue_prefix + shard_id].extend(
                        [value.to_json() for value in values])

                    # determine scores for stations
                    if userid is not None:
                        new_station_count[name] += self.new_stations(
                            session, shard_key, values)

        return (obs_queue, malformed_reports, obs_count,
                positions, new_station_count)

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

    def process_datamap(self, positions):
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
            queue.enqueue(list(values), pipe=self.pipe, json=False)

    def process_score(self, userid, pos_count, new_station_count):
        if userid is None or pos_count <= 0:
            return

        scores = []
        key = Score.to_hashkey(
            userid=userid,
            key=ScoreKey.location,
            time=None)
        scores.append({'hashkey': key, 'value': pos_count})

        for name, score_key in (('cell', ScoreKey.new_cell),
                                ('wifi', ScoreKey.new_wifi)):
            count = new_station_count[name]
            if count <= 0:
                continue
            key = Score.to_hashkey(
                userid=userid,
                key=score_key,
                time=None)
            scores.append({'hashkey': key, 'value': count})

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
