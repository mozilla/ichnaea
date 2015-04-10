from datetime import datetime
import time

from pyramid.httpexceptions import (
    HTTPOk,
    HTTPServiceUnavailable,
)
from pytz import utc
from redis import ConnectionError

from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import BaseSubmitter
from ichnaea.service.error import JSONParseError
from ichnaea.service.geosubmit.schema import GeoSubmitBatchSchema


def configure_geosubmit(config):
    config.add_route('v1_geosubmit', '/v1/geosubmit')
    config.add_view(geosubmit_view, route_name='v1_geosubmit', renderer='json')


class GeoSubmitter(BaseSubmitter):

    schema = GeoSubmitBatchSchema
    error_response = JSONParseError

    def prepare_measure_data(self, request_data):
        batch_list = []
        for batch in request_data['items']:
            normalized_cells = []
            for c in batch['cellTowers']:
                cell_radio = c['radioType']
                if not cell_radio:
                    cell_radio = batch['radioType']
                cell = {}
                cell['radio'] = cell_radio
                cell['mcc'] = c['mobileCountryCode']
                cell['mnc'] = c['mobileNetworkCode']
                cell['lac'] = c['locationAreaCode']
                cell['cid'] = c['cellId']
                cell['psc'] = c['psc']
                cell['asu'] = c['asu']
                cell['signal'] = c['signalStrength']
                cell['ta'] = c['timingAdvance']
                normalized_cells.append(cell)

            normalized_wifi = []
            for w in batch['wifiAccessPoints']:
                wifi = {}
                wifi['key'] = w['macAddress']
                wifi['frequency'] = w['frequency']
                wifi['channel'] = w['channel']
                wifi['signal'] = w['signalStrength']
                wifi['snr'] = w['signalToNoiseRatio']
                normalized_wifi.append(wifi)

            timestamp = batch['timestamp']
            if timestamp == 0:
                timestamp = time.time() * 1000.0

            dt = utc.fromutc(datetime.utcfromtimestamp(
                             timestamp / 1000.0).replace(tzinfo=utc))

            normalized_batch = {'lat': batch['latitude'],
                                'lon': batch['longitude'],
                                'time': dt,
                                'accuracy': batch['accuracy'],
                                'altitude': batch['altitude'],
                                'altitude_accuracy': batch['altitudeAccuracy'],
                                'heading': batch['heading'],
                                'speed': batch['speed'],
                                'cell': normalized_cells,
                                'wifi': normalized_wifi,
                                }
            batch_list.append(normalized_batch)
        return batch_list


@check_api_key('geosubmit')
def geosubmit_view(request):
    submitter = GeoSubmitter(request)

    # may raise HTTP error
    request_data = submitter.preprocess()

    try:
        submitter.insert_measures(request_data)
    except ConnectionError:  # pragma: no cover
        return HTTPServiceUnavailable()

    result = HTTPOk()
    result.content_type = 'application/json'
    result.body = '{}'
    return result
