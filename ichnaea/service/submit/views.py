import calendar
import copy
import time

import iso8601
from pyramid.httpexceptions import (
    HTTPNoContent,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.service.error import JSONError
from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import BaseSubmitter
from ichnaea.service.submit.schema import SubmitSchema


def configure_submit(config):
    config.add_route('v1_submit', '/v1/submit')
    config.add_view(submit_view, route_name='v1_submit', renderer='json')


class Submitter(BaseSubmitter):

    schema = SubmitSchema
    error_response = JSONError

    def prepare_measure_data(self, request_data):
        reports = []
        for item in request_data['items']:
            report = copy.deepcopy(item)
            report_radio = report['radio']
            for cell in report['cell']:
                if cell['radio'] is None:
                    cell['radio'] = report_radio
            reports.append(report)
            if 'radio' in report:
                del report['radio']
        return reports

    def prepare_reports(self, request_data):
        def conditional_set(item, target, value, missing):
            if value != missing:
                item[target] = value

        position_map = [
            ('latitude', 'lat', None),
            ('longitude', 'lon', None),
            ('accuracy', 'accuracy', 0),
            ('altitude', 'altitude', 0),
            ('altitudeAccuracy', 'altitude_accuracy', 0),
            ('age', 'age', None),
            ('heading', 'heading', -1.0),
            ('pressure', 'pressure', None),
            ('speed', 'speed', -1.0),
            ('source', 'source', 'gps'),
        ]

        cell_map = [
            ('radioType', 'radio', None),
            ('mobileCountryCode', 'mcc', -1),
            ('mobileNetworkCode', 'mnc', -1),
            ('locationAreaCode', 'lac', -1),
            ('cellId', 'cid', -1),
            ('age', 'age', None),
            ('asu', 'asu', -1),
            ('primaryScramblingCode', 'psc', -1),
            ('serving', 'serving', None),
            ('signalStrength', 'signal', 0),
            ('timingAdvance', 'ta', 0),
        ]

        wifi_map = [
            ('macAddress', 'key', None),
            ('radioType', 'radio', None),
            ('age', 'age', None),
            ('channel', 'channel', 0),
            ('frequency', 'frequency', 0),
            ('signalToNoiseRatio', 'signalToNoiseRatio', 0),
            ('signalStrength', 'signal', 0),
        ]

        reports = []
        for item in request_data['items']:
            report = {}

            # parse date string to unixtime, default to now
            timestamp = time.time() * 1000.0
            if item['time'] != '':
                try:
                    dt = iso8601.parse_date(item['time'])
                    calendar.timegm(dt.timetuple()) * 1000.0
                except (iso8601.ParseError, TypeError):  # pragma: no cover
                    pass
            report['timestamp'] = timestamp

            position = {}
            for target, source, missing in position_map:
                conditional_set(position, target, item[source], missing)
            if position:
                report['position'] = position

            cells = []
            item_radio = item['radio']
            for cell_item in item['cell']:
                cell = {}
                for target, source, missing in cell_map:
                    conditional_set(cell, target, cell_item[source], missing)
                if cell:
                    if 'radioType' not in cell and item_radio:
                        cell['radioType'] = item_radio
                    if cell['radioType'] == 'umts':
                        cell['radioType'] = 'wcdma'
                    cells.append(cell)

            if cells:
                report['cellTowers'] = cells

            wifis = []
            for wifi_item in item['wifi']:
                wifi = {}
                for target, source, missing in wifi_map:
                    conditional_set(wifi, target, wifi_item[source], missing)
                if wifi:
                    wifis.append(wifi)

            if wifis:
                report['wifiAccessPoints'] = wifis

            if cells or wifis:
                reports.append(report)

        return reports


@check_api_key('submit', error_on_invalidkey=False)
def submit_view(request, api_key):
    submitter = Submitter(request, api_key)

    # may raise HTTP error
    request_data = submitter.preprocess()

    try:
        submitter.insert_measures(request_data)
    except ConnectionError:  # pragma: no cover
        return HTTPServiceUnavailable()

    try:
        submitter.submit(request_data)
    except ConnectionError:  # pragma: no cover
        # secondary pipeline is considered non-essential for now
        pass

    return HTTPNoContent()
