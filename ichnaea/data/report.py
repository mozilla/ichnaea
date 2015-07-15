from collections import defaultdict

from ichnaea.data.base import DataTask
from ichnaea.models import (
    CellObservation,
    CellReport,
    Report,
    Score,
    ScoreKey,
    User,
    WifiObservation,
    WifiReport,
)
from ichnaea.models.cell import encode_radio_dict


class ReportQueue(DataTask):

    def __init__(self, task, session, pipe, api_key=None,
                 email=None, ip=None, nickname=None,
                 insert_cell_task=None, insert_wifi_task=None):
        DataTask.__init__(self, task, session)
        self.pipe = pipe
        self.api_key = api_key
        self.email = email
        self.ip = ip
        self.nickname = nickname
        self.insert_cell_task = insert_cell_task
        self.insert_wifi_task = insert_wifi_task

    def insert(self, reports):
        length = len(reports)
        userid = self.process_user(self.nickname, self.email)

        self.process_reports(reports, userid=userid)

        self.stats_client.incr('items.uploaded.reports', length)
        if self.api_key and self.api_key.log:
            self.stats_client.incr(
                'items.api_log.%s.uploaded.reports' % self.api_key.name,
                length)

        return length

    def process_reports(self, reports, userid=None):
        positions = set()
        observations = {'cell': [], 'wifi': []}

        for report in reports:
            cell, wifi = self.process_report(report)
            if cell:
                observations['cell'].extend(cell)
            if wifi:
                observations['wifi'].extend(wifi)
            if (cell or wifi):
                positions.add((report['lat'], report['lon']))

        for name, log_name, task in (
                ('cell', 'cell_observations', self.insert_cell_task),
                ('wifi', 'wifi_observations', self.insert_wifi_task)):

            if observations[name]:
                # group by and create task per small batch of keys
                self.stats_client.incr('items.uploaded.%s' % log_name,
                                       len(observations[name]))

                if self.api_key and self.api_key.log:
                    self.stats_client.incr(
                        'items.api_log.%s.uploaded.%s' % (
                            self.api_key.name, log_name),
                        len(observations[name]))

                station_obs = defaultdict(list)
                for obs in observations[name]:
                    station_obs[obs.hashkey()].append(obs.__dict__)

                batch_size = 100
                countdown = 0
                stations = list(station_obs.values())

                for i in range(0, len(stations), batch_size):
                    values = []
                    for obs_batch in stations[i:i + batch_size]:
                        if name == 'cell':
                            values.extend(
                                [encode_radio_dict(o) for o in obs_batch])
                        elif name == 'wifi':
                            values.extend(obs_batch)
                    # insert observations, expire the task if it wasn't
                    # processed after six hours to avoid queue overload,
                    # also delay each task by one second more, to get a
                    # more even workload and avoid parallel updates of
                    # the same underlying stations
                    task.apply_async(
                        args=[values],
                        kwargs={'userid': userid},
                        expires=21600,
                        countdown=countdown)
                    countdown += 1

        self.process_mapstat(positions)
        self.process_score(userid, positions)

    def process_report(self, data):
        report = Report.create(**data)
        if report is None:
            return (None, None)

        observations = {'cell': {}, 'wifi': {}}

        for name, report_cls, obs_cls in (
                ('cell', CellReport, CellObservation),
                ('wifi', WifiReport, WifiObservation)):
            observations[name] = {}

            if data.get(name):
                for item in data[name]:
                    # validate the cell/wifi specific fields
                    item_report = report_cls.create(**item)
                    if item_report is None:
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

        return (observations['cell'].values(), observations['wifi'].values())

    def process_mapstat(self, positions):
        if not positions:
            return

        queue = self.task.app.data_queues['update_mapstat']
        positions = [{'lat': lat, 'lon': lon} for lat, lon in positions]
        queue.enqueue(positions, pipe=self.pipe)

    def process_score(self, userid, positions):
        if userid is None or len(positions) <= 0:
            return

        queue = self.task.app.data_queues['update_score']
        key = Score.to_hashkey(
            userid=userid,
            key=ScoreKey.location,
            time=None)
        queue.enqueue([{'hashkey': key, 'value': len(positions)}])

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
