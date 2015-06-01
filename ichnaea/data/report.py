from collections import defaultdict
import uuid

from ichnaea.customjson import encode_radio_dict
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
            report['report_id'] = uuid.uuid1()
            cell, wifi = self.process_report(report)
            cell_observations.extend(cell)
            wifi_observations.extend(wifi)
            if cell or wifi:
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

            # Create a task per group of 5 cell keys at a time.
            # Grouping them helps in avoiding per-task overhead.
            cells = list(cells.values())
            batch_size = 5
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

            # Create a task per group of 20 WiFi keys at a time.
            # We tend to get a huge number of unique WiFi networks per
            # batch upload, with one to very few observations per WiFi.
            # Grouping them helps in avoiding per-task overhead.
            wifis = list(wifis.values())
            batch_size = 20
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
        def add_missing_dict_entries(dst, src):
            # x.update(y) overwrites entries in x with those in y;
            # We want to only add those not already present.
            # We also only want to copy the top-level base report data
            # and not any nested values like cell or wifi.
            for (key, value) in src.items():
                if key != 'radio' and key not in dst \
                   and not isinstance(value, (tuple, list, dict)):
                    dst[key] = value

        report_data = Report.validate(data)
        if report_data is None:
            return ([], [])

        cell_observations = {}
        wifi_observations = {}

        if data.get('cell'):
            # flatten report / cell data into a single dict
            for cell in data['cell']:
                # only validate the additional fields
                cell = CellReport.validate(cell)
                if cell is None:
                    continue
                add_missing_dict_entries(cell, report_data)
                cell_key = CellObservation.to_hashkey(cell)
                if cell_key in cell_observations:
                    existing = cell_observations[cell_key]
                    if existing['ta'] > cell['ta'] or \
                       (existing['signal'] != 0 and
                        existing['signal'] < cell['signal']) or \
                       existing['asu'] < cell['asu']:
                        cell_observations[cell_key] = cell
                else:
                    cell_observations[cell_key] = cell
        cell_observations = cell_observations.values()

        # flatten report / wifi data into a single dict
        if data.get('wifi'):
            for wifi in data['wifi']:
                # only validate the additional fields
                wifi = WifiReport.validate(wifi)
                if wifi is None:
                    continue
                add_missing_dict_entries(wifi, report_data)
                wifi_key = WifiObservation.to_hashkey(wifi)
                if wifi_key in wifi_observations:
                    existing = wifi_observations[wifi_key]
                    if existing['signal'] != 0 and \
                       existing['signal'] < wifi['signal']:
                        wifi_observations[wifi_key] = wifi
                else:
                    wifi_observations[wifi_key] = wifi
            wifi_observations = wifi_observations.values()
        return (cell_observations, wifi_observations)

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
