from collections import defaultdict

from sqlalchemy.orm import load_only

from ichnaea.data.base import DataTask
from ichnaea.models import (
    Cell,
    CellBlocklist,
    CellObservation,
    CellReport,
    Report,
    Score,
    ScoreKey,
    User,
    Wifi,
    WifiBlocklist,
    WifiObservation,
    WifiReport,
)


class ReportQueue(DataTask):

    def __init__(self, task, session, pipe, api_key=None,
                 email=None, ip=None, nickname=None):
        DataTask.__init__(self, task, session)
        self.pipe = pipe
        self.api_key = api_key
        self.email = email
        self.ip = ip
        self.nickname = nickname
        self.cell_queue = self.task.app.data_queues['update_cell']
        self.wifi_queue = self.task.app.data_queues['update_wifi']

    def emit_stats(self, reports, malformed_reports, obs_count):
        api_tag = []
        if self.api_key and self.api_key.log:
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

    def new_stations(self, model, block_model, station_keys):
        if len(station_keys) == 0:
            return 0

        # assume all stations are unknown
        unknown_keys = set(station_keys)

        # first check the station table, which is more likely to contain
        # stations
        station_iter = model.iterkeys(
            self.session,
            list(unknown_keys),
            # only load the columns required for the hashkey
            extra=lambda query: query.options(
                load_only(*tuple(model._hashkey_cls._fields))))
        # subtract all stations which are found in the station table
        unknown_keys -= set([station.hashkey() for station in station_iter])
        if len(unknown_keys) == 0:  # pragma: no cover
            return 0

        # Only check the blocklist table for the still unknown keys.
        # There is no need to check for the already found keys again.
        block_iter = block_model.iterkeys(
            self.session,
            list(unknown_keys),
            # only load the columns required for the hashkey
            extra=lambda query: query.options(
                load_only(*tuple(block_model._hashkey_cls._fields))))
        # subtract all stations which are found in the blocklist table
        unknown_keys -= set([block.hashkey() for block in block_iter])

        return len(unknown_keys)

    def insert(self, reports):
        length = len(reports)
        userid = self.process_user(self.nickname, self.email)
        self.process_reports(reports, userid=userid)
        return length

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
        station_obs = {'cell': defaultdict(list), 'wifi': defaultdict(list)}
        for name, model in (('cell', Cell),
                            ('wifi', Wifi)):
            for obs in observations[name]:
                station_obs[name][model.to_hashkey(obs)].append(obs)

        # determine scores for stations
        for name, model, block_model in (('cell', Cell, CellBlocklist),
                                         ('wifi', Wifi, WifiBlocklist)):
            new_station_count[name] += self.new_stations(
                model, block_model, list(station_obs[name].keys()))

        for name, queue in (('cell', self.cell_queue),
                            ('wifi', self.wifi_queue)):
            if observations[name]:
                queue.enqueue(list(observations[name]), pipe=self.pipe)

        self.process_mapstat(positions)
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
                    item_key = item_obs.hashkey()

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

    def process_mapstat(self, positions):
        if not positions:
            return

        queue = self.task.app.data_queues['update_mapstat']
        positions = [{'lat': lat, 'lon': lon} for lat, lon in positions]
        queue.enqueue(positions, pipe=self.pipe)

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
