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
        cell_observations = []
        wifi_observations = []
        for i, report in enumerate(reports):
            cell, wifi = self.process_report(report)
            cell_observations.extend(cell)
            wifi_observations.extend(wifi)
            if (cell or wifi) and report.get('lat') and report.get('lon'):
                positions.add((report['lat'], report['lon']))

        if cell_observations:
            # group by and create task per cell key
            self.stats_client.incr('items.uploaded.cell_observations',
                                   len(cell_observations))
            if self.api_key and self.api_key.log:
                self.stats_client.incr(
                    'items.api_log.%s.uploaded.'
                    'cell_observations' % self.api_key.name,
                    len(cell_observations))

            cells = defaultdict(list)
            for obs in cell_observations:
                cells[CellObservation.to_hashkey(obs)].append(obs)

            # Create a task per group of 100 cell keys at a time.
            # Grouping them helps in avoiding per-task overhead.
            cells = list(cells.values())
            batch_size = 100
            countdown = 0
            for i in range(0, len(cells), batch_size):
                values = []
                for observations in cells[i:i + batch_size]:
                    values.extend([encode_radio_dict(o) for o in observations])
                # insert observations, expire the task if it wasn't processed
                # after six hours to avoid queue overload, also delay
                # each task by one second more, to get a more even workload
                # and avoid parallel updates of the same underlying stations
                self.insert_cell_task.apply_async(
                    args=[values],
                    kwargs={'userid': userid},
                    expires=21600,
                    countdown=countdown)
                countdown += 1

        if wifi_observations:
            # group by WiFi key
            self.stats_client.incr('items.uploaded.wifi_observations',
                                   len(wifi_observations))
            if self.api_key and self.api_key.log:
                self.stats_client.incr(
                    'items.api_log.%s.uploaded.'
                    'wifi_observations' % self.api_key.name,
                    len(wifi_observations))

            wifis = defaultdict(list)
            for obs in wifi_observations:
                wifis[WifiObservation.to_hashkey(obs)].append(obs)

            # Create a task per group of 100 WiFi keys at a time.
            # We tend to get a huge number of unique WiFi networks per
            # batch upload, with one to very few observations per WiFi.
            # Grouping them helps in avoiding per-task overhead.
            wifis = list(wifis.values())
            batch_size = 100
            countdown = 0
            for i in range(0, len(wifis), batch_size):
                values = []
                for observations in wifis[i:i + batch_size]:
                    values.extend(observations)
                # insert observations, expire the task if it wasn't processed
                # after six hours to avoid queue overload, also delay
                # each task by one second more, to get a more even workload
                # and avoid parallel updates of the same underlying stations
                self.insert_wifi_task.apply_async(
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
            return ([], [])

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

                # don't expose observation classes to the outside yet
                observations[name] = [
                    obs.__dict__ for obs in observations[name].values()]

        return (observations['cell'], observations['wifi'])

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
