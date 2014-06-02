from datetime import datetime
import time
from pyramid.httpexceptions import HTTPNotFound, HTTPOk
from pytz import utc

from ichnaea.decimaljson import dumps
from ichnaea.heka_logging import get_heka_client
from ichnaea.service.base import check_api_key

from ichnaea.service.error import (
    JSONError,
    MSG_ONE_OF,
    preprocess_request,
    verify_schema,
)


from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.geolocate.views import (
    NOT_FOUND,
    do_geolocate,
    geolocate_validator,
)

from ichnaea.service.geosubmit.schema import (
    GeoSubmitBatchSchema,
    GeoSubmitSchema,
)


from ichnaea.service.submit.schema import SubmitSchema
from ichnaea.service.submit.tasks import insert_measures


def geosubmit_validator(data, errors):
    if errors:
        # don't add this error if something else was already wrong
        return
    if 'items' in data:
        chunk_list = data['items']
    else:
        chunk_list = [data]
    for chunk in chunk_list:
        cell = chunk.get('cellTowers', ())
        wifi = chunk.get('wifiAccessPoints', ())

        if chunk['timestamp'] == 0:
            chunk['timestamp'] = time.time()*1000.0

        if not any(wifi) and not any(cell):
            errors.append(dict(name='body', description=MSG_ONE_OF))


def process_upload(nickname, items):
    if isinstance(nickname, str):
        nickname = nickname.decode('utf-8', 'ignore')

    batch_list = []
    for batch in items:
        normalized_cells = []
        for c in batch['cellTowers']:
            cell = {}
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
            normalized_wifi.append(wifi)

        dt = utc.fromutc(datetime.utcfromtimestamp(
                         batch['timestamp']/1000.0).replace(tzinfo=utc))
        ts = dt.isoformat()

        normalized_batch = {'lat': batch['latitude'] / (10**7),
                            'lon': batch['longitude'] / (10**7),
                            'time': ts,
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

    # Run the SubmitScheme validator against the normalized submit
    # data.
    schema = SubmitSchema()
    body = {'items': batch_list}
    errors = []
    validated = {}
    verify_schema(schema, body, errors, validated)

    if errors:
        # Short circuit on any error in schema validation
        return validated, errors

    for i in range(0, len(batch_list), 100):
        insert_measures.delay(
            items=dumps(batch_list[i:i + 100]),
            nickname=nickname,
        )
    return validated, errors


def configure_geosubmit(config):
    config.add_route('v1_geosubmit', '/v1/geosubmit')
    config.add_view(geosubmit_view, route_name='v1_geosubmit', renderer='json')


@check_api_key('geosubmit', True)
def geosubmit_view(request):
    # Order matters here.  We need to try the batch mode *before* the
    # single upload mode as classic w3c geolocate calls should behave
    # identically using either geosubmit or geolocate
    data, errors = preprocess_request(
        request,
        schema=GeoSubmitBatchSchema(),
        extra_checks=(geosubmit_validator, ),
        response=None,
    )

    if any(data.get('items', ())):
        # TODO: process batch mode
        return process_batch(request, data, errors)
    else:
        return process_single(request)


def process_batch(request, data, errors):
    heka_client = get_heka_client()
    nickname = request.headers.get('X-Nickname', u'')
    validated, errors = process_upload(nickname, data['items'])

    if errors:
        heka_client.incr('geosubmit.upload.errors', len(errors))

    result = HTTPOk()
    result.content_type = 'application/json'
    result.body = dumps({})
    return result


def process_single(request):
    heka_client = get_heka_client()

    locate_data, locate_errors = preprocess_request(
        request,
        schema=GeoLocateSchema(),
        extra_checks=(geolocate_validator, ),
        response=JSONError,
        accept_empty=True,
    )

    data, errors = preprocess_request(
        request,
        schema=GeoSubmitSchema(),
        extra_checks=(geosubmit_validator, ),
        response=None,
    )
    data = {'items': [data]}

    session = request.db_slave_session

    nickname = request.headers.get('X-Nickname', u'')
    validated, errors = process_upload(nickname, data['items'])

    if errors:
        heka_client.incr('geosubmit.upload.errors', len(errors))

    result = do_geolocate(session,
                          request,
                          data['items'][0],
                          heka_client,
                          'geosubmit')

    if result is None:
        heka_client.incr('geosubmit.miss')
        result = HTTPNotFound()
        result.content_type = 'application/json'
        result.body = NOT_FOUND
        return result

    return {
        "location": {
            "lat": result['lat'],
            "lng": result['lon'],
        },
        "accuracy": float(result['accuracy']),
    }
