from collections import defaultdict
from datetime import datetime

import pytz
import simplejson

from ichnaea.internaljson import internal_dumps
from ichnaea.data.export import (
    MetadataGroup,
    ReportUploader,
)


class InternalTransform(object):

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

    def conditional_set(self, item, target, value):
        if value is not None:
            item[target] = value

    def _map_dict(self, item_source, field_map):
        value = {}
        for spec in field_map:
            if isinstance(spec, tuple):
                source, target = spec
            else:
                source = spec
                target = spec
            self.conditional_set(value, target,
                                 item_source.get(source))
        return value

    def _parse_dict(self, item, report, key_map, field_map):
        value = {}
        if key_map[0] is None:  # pragma: no cover
            item_source = item
        else:
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

    def _parse_cells(self, item, report, key_map, field_map):
        cells = []
        for cell_item in item.get(key_map[0], ()):
            cell = self._map_dict(cell_item, field_map)
            if cell:
                cells.append(cell)
        if cells:
            report[key_map[1]] = cells
        return cells

    def __call__(self, item):
        report = {}
        self._parse_dict(item, report, self.position_id, self.position_map)

        timestamp = item.get('timestamp')
        if timestamp:
            report['timestamp'] = timestamp

        cells = self._parse_cells(item, report, self.cell_id, self.cell_map)
        wifis = self._parse_list(item, report, self.wifi_id, self.wifi_map)

        if cells or wifis:
            return report
        return {}


class InternalUploader(ReportUploader):

    transform = InternalTransform()

    @staticmethod
    def _task():
        # avoiding import cycle problems, sigh!
        from ichnaea.data.tasks import insert_measures
        return insert_measures

    def _format_report(self, item):
        report = self.transform(item)

        timestamp = report.pop('timestamp', None)
        if timestamp:
            dt = datetime.utcfromtimestamp(timestamp / 1000.0)
            report['time'] = dt.replace(microsecond=0, tzinfo=pytz.UTC)

        return report

    def send(self, url, data):
        groups = defaultdict(list)
        for item in simplejson.loads(data):
            group = MetadataGroup(**item['metadata'])
            report = self._format_report(item['report'])
            if report:
                groups[group].append(report)

        for group, reports in groups.items():
            self._task().apply_async(
                kwargs={
                    'api_key_text': group.api_key,
                    'email': group.email,
                    'ip': group.ip,
                    'items': internal_dumps(reports),
                    'nickname': group.nickname,
                },
                expires=21600)
