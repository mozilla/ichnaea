from collections import defaultdict

from ichnaea.data.base import DataTask
from ichnaea.models import (
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


class ReportQueue(DataTask):

    def __init__(self, task, session, pipe, api_key=None,
                 email=None, ip=None, nickname=None):
        DataTask.__init__(self, task, session)
        self.pipe = pipe
        self.api_key = api_key
        self.email = email
        self.ip = ip
        self.nickname = nickname
        self.data_queues = self.task.app.data_queues

    def __call__(self, reports):
        userid = self.process_user(self.nickname, self.email)
        self.process_reports(reports, userid=userid)

    def emit_stats(self, reports, malformed_reports, obs_count):
        api_tag = []
        if self.api_key and self.api_key.should_log('submit'):
            api_tag = ['key:%s' % self.api_key.name]

        if reports > 0:
            self.stats_client.incr(
                'data.report.upload', reports, tags=api_tag)

        if malformed_reports > 0:
            self.stats_client.incr(
                'data.report.drop', malformed_reports,
                tags=['reason:malformed'] + api_tag)

        for name, stats in obs_count.items():
            for action, count in stats.items():
                if count > 0:
                    tags = ['type:%s' % name]
                    if action == 'drop':
                        tags.append('reason:malformed')
                    self.stats_client.incr(
                        'data.observation.%s' % action,
                        count,
                        tags=tags + api_tag)

    def new_stations(self, name, station_keys):
        if len(station_keys) == 0:
            return 0

        if name == 'cell':
            model = CellShard
            key_id = 'cellid'
        elif name == 'wifi':
            model = WifiShard
            key_id = 'mac'

        # assume all stations are unknown
        unknown_keys = set(station_keys)

        shards = defaultdict(list)
        for key in unknown_keys:
            shards[model.shard_model(key)].append(key)

        for shard, keys in shards.items():
            key_column = getattr(shard, key_id)
            query = (self.session.query(key_column)
                                 .filter(key_column.in_(keys)))
            unknown_keys -= set([getattr(r, key_id) for r in query.all()])

        return len(unknown_keys)

    def process_reports(self, reports, userid=None):
        malformed_reports = 0
        positions = set()
        observations = {'cell': [], 'wifi': []}
        obs_count = {
            'cell': {'upload': 0, 'drop': 0},
            'wifi': {'upload': 0, 'drop': 0},
        }
        new_station_count = {'cell': 0, 'wifi': 0}

        for report in reports:
            cell, wifi, malformed_obs = self.process_report(report)
            if cell:
                observations['cell'].extend(cell)
                obs_count['cell']['upload'] += len(cell)
            if wifi:
                observations['wifi'].extend(wifi)
                obs_count['wifi']['upload'] += len(wifi)
            if (cell or wifi):
                positions.add((report['lat'], report['lon']))
            else:
                malformed_reports += 1
            for name in ('cell', 'wifi'):
                obs_count[name]['drop'] += malformed_obs[name]

        # group by unique station key
        for name in ('cell', 'wifi'):
            station_keys = set()
            for obs in observations[name]:
                if name == 'cell':
                    station_keys.add(obs.cellid)
                elif name == 'wifi':
                    station_keys.add(obs.mac)
            # determine scores for stations
            new_station_count[name] += self.new_stations(name, station_keys)

        if observations['cell']:
            sharded_obs = defaultdict(list)
            for ob in observations['cell']:
                shard_id = CellShard.shard_id(ob.cellid)
                sharded_obs[shard_id].append(ob)
            for shard_id, values in sharded_obs.items():
                cell_queue = self.data_queues['update_cell_' + shard_id]
                cell_queue.enqueue(list(values), pipe=self.pipe)

        if observations['wifi']:
            sharded_obs = defaultdict(list)
            for ob in observations['wifi']:
                shard_id = WifiShard.shard_id(ob.mac)
                sharded_obs[shard_id].append(ob)
            for shard_id, values in sharded_obs.items():
                wifi_queue = self.data_queues['update_wifi_' + shard_id]
                wifi_queue.enqueue(list(values), pipe=self.pipe)

        self.process_datamap(positions)
        self.process_score(userid, positions, new_station_count)
        self.emit_stats(
            len(reports),
            malformed_reports,
            obs_count,
        )

    def process_report(self, data):
        malformed = {'cell': 0, 'wifi': 0}
        observations = {'cell': {}, 'wifi': {}}

        report = Report.create(**data)
        if report is None:
            return (None, None, malformed)

        for name, report_cls, obs_cls in (
                ('cell', CellReport, CellObservation),
                ('wifi', WifiReport, WifiObservation)):
            observations[name] = {}

            if data.get(name):
                for item in data[name]:
                    # validate the cell/wifi specific fields
                    item_report = report_cls.create(**item)
                    if item_report is None:
                        malformed[name] += 1
                        continue

                    # combine general and specific report data into one
                    item_obs = obs_cls.combine(report, item_report)
                    item_key = item_obs.unique_key

                    # if we have better data for the same key, ignore
                    existing = observations[name].get(item_key)
                    if existing is not None:
                        if existing.better(item_obs):
                            continue

                    observations[name][item_key] = item_obs

        return (
            observations['cell'].values(),
            observations['wifi'].values(),
            malformed,
        )

    def process_datamap(self, positions):
        if not positions:
            return

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

    def process_score(self, userid, positions, new_station_count):
        if userid is None or len(positions) <= 0:
            return

        queue = self.task.app.data_queues['update_score']
        scores = []

        key = Score.to_hashkey(
            userid=userid,
            key=ScoreKey.location,
            time=None)
        scores.append({'hashkey': key, 'value': len(positions)})

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

        queue.enqueue(scores)

    def process_user(self, nickname, email):
        userid = None
        if not email or len(email) > 255:
            email = u''
        if nickname and (2 <= len(nickname) <= 128):
            # automatically create user objects and update nickname
            rows = self.session.query(User).filter(User.nickname == nickname)
            old = rows.first()
            if not old:
                user = User(
                    nickname=nickname,
                    email=email
                )
                self.session.add(user)
                self.session.flush()
                userid = user.id
            else:
                userid = old.id
                # update email column on existing user
                if old.email != email:
                    old.email = email

        return userid
