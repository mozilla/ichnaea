from datetime import datetime
import time

from pyramid.httpexceptions import (
    HTTPOk,
    HTTPServiceUnavailable,
)
from pytz import utc
from redis import ConnectionError

from ichnaea.customjson import kombu_dumps
from ichnaea.data.tasks import insert_measures
from ichnaea.logging import RAVEN_ERROR
from ichnaea.service.base import check_api_key
from ichnaea.service.error import (
    JSONParseError,
    preprocess_request,
)
from ichnaea.service.geosubmit.schema import GeoSubmitBatchSchema


def map_items(items):
    batch_list = []
    for batch in items:
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

        if batch['timestamp'] == 0:
            batch['timestamp'] = time.time() * 1000.0

        dt = utc.fromutc(datetime.utcfromtimestamp(
                         batch['timestamp'] / 1000.0).replace(tzinfo=utc))

        normalized_batch = {'lat': batch['latitude'],
                            'lon': batch['longitude'],
                            'time': dt,
                            'accuracy': batch['accuracy'],
                            'altitude': batch['altitude'],
                            'altitude_accuracy': batch['altitudeAccuracy'],
                            'radio': batch['radioType'],
                            'heading': batch['heading'],
                            'speed': batch['speed'],
                            'cell': normalized_cells,
                            'wifi': normalized_wifi,
                            }
        batch_list.append(normalized_batch)
    return batch_list


def configure_geosubmit(config):
    config.add_route('v1_geosubmit', '/v1/geosubmit')
    config.add_view(geosubmit_view, route_name='v1_geosubmit', renderer='json')


@check_api_key('geosubmit')
def geosubmit_view(request):
    stats_client = request.registry.stats_client
    api_key_log = getattr(request, 'api_key_log', False)
    api_key_name = getattr(request, 'api_key_name', None)

    try:
        data, errors = preprocess_request(
            request,
            schema=GeoSubmitBatchSchema(),
            response=JSONParseError,
        )
    except JSONParseError:  # pragma: no cover
        # capture JSON exceptions for submit calls
        request.registry.heka_client.raven(RAVEN_ERROR)
        raise

    items = map_items(data['items'])
    nickname = request.headers.get('X-Nickname', u'')
    if isinstance(nickname, str):  # pragma: no cover
        nickname = nickname.decode('utf-8', 'ignore')

    email = request.headers.get('X-Email', u'')
    if isinstance(email, str):  # pragma: no cover
        email = email.decode('utf-8', 'ignore')

    # count the number of batches and emit a pseudo-timer to capture
    # the number of reports per batch
    length = len(items)
    stats_client.incr('items.uploaded.batches')
    stats_client.timing('items.uploaded.batch_size', length)

    if api_key_log:
        stats_client.incr(
            'items.api_log.%s.uploaded.batches' % api_key_name)
        stats_client.timing(
            'items.api_log.%s.uploaded.batch_size' % api_key_name, length)

    # batch incoming data into multiple tasks, in case someone
    # manages to submit us a huge single request
    for i in range(0, length, 100):
        batch = kombu_dumps(items[i:i + 100])
        # insert observations, expire the task if it wasn't processed
        # after six hours to avoid queue overload
        try:
            insert_measures.apply_async(
                kwargs={
                    'email': email,
                    'items': batch,
                    'nickname': nickname,
                    'api_key_log': api_key_log,
                    'api_key_name': api_key_name,
                },
                expires=21600)
        except ConnectionError:  # pragma: no cover
            return HTTPServiceUnavailable()

    result = HTTPOk()
    result.content_type = 'application/json'
    result.body = '{}'
    return result
