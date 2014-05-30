from datetime import datetime
import time
from pyramid.httpexceptions import HTTPNotFound

from ichnaea.decimaljson import dumps
from ichnaea.heka_logging import get_heka_client
from ichnaea.service.base import check_api_key
from ichnaea.service.error import (
    JSONError,
    MSG_ONE_OF,
    preprocess_request,
    verify_schema,
)
from ichnaea.service.geolocate.views import (
    NOT_FOUND,
    do_geolocate,
)
from ichnaea.service.geosubmit.schema import GeoSubmitSchema
from ichnaea.service.submit.schema import SubmitSchema
from ichnaea.service.submit.tasks import insert_measures

from pytz import utc


def geosubmit_validator(data, errors):
    if errors:
        # don't add this error if something else was already wrong
        return
    cell = data.get('cellTowers', ())
    wifi = data.get('wifiAccessPoints', ())

    if data['timestamp'] == 0:
        data['timestamp'] = time.time()*1000.0

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
    heka_client = get_heka_client()

    data, errors = preprocess_request(
        request,
        schema=GeoSubmitSchema(),
        extra_checks=(geosubmit_validator, ),
        response=JSONError,
    )

    session = request.db_slave_session

    result = do_geolocate(session,
                          request,
                          data,
                          heka_client,
                          'geosubmit')

    items = data.get('items', [data])
    nickname = request.headers.get('X-Nickname', u'')
    validated, errors = process_upload(nickname, items)

    if errors:
        heka_client.incr('geosubmit.upload.errors', len(errors))

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
