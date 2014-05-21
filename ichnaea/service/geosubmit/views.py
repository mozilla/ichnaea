from pyramid.httpexceptions import HTTPNotFound
from ichnaea.heka_logging import get_heka_client
from ichnaea.service.base import check_api_key
from ichnaea.service.errors import JSONError
from ichnaea.service.geolocate.views import (
    NOT_FOUND,
)
from ichnaea.service.geosubmit.schema import GeoSubmitSchema
from ichnaea.service.error import (
    MSG_BAD_RADIO,
    MSG_ONE_OF,
    preprocess_request,
)

from ichnaea.service.geolocate.views import (
    search_wifi_ap,
    search_cell_tower,
    search_cell_tower_lac,
)
from ichnaea.service.search.views import (
    search_geoip,
)
from ichnaea.service.submit.tasks import insert_measures
from ichnaea.decimaljson import dumps


def geosubmit_validator(data, errors):
    if errors:
        # don't add this error if something else was already wrong
        return
    cell = data.get('cellTowers', ())
    wifi = data.get('wifiAccessPoints', ())

    # If a radio field is populated in any one of the cells in
    # cellTowers, this is a buggy geolocate call from FirefoxOS.
    # Just assume that we want to use the radio field in cellTowers
    if data['radioType'] == '':
        for c in cell:
            cell_radio = c['radio']
            if cell_radio != '' and data['radioType'] == '':
                data['radioType'] = cell_radio
            elif cell_radio != '' and data['radioType'] != cell_radio:
                errors.append(dict(name='body', description=MSG_BAD_RADIO))
                break

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
            cell['radio'] = c['radio']
            cell['mcc'] = c['mobileCountryCode']
            cell['mnc'] = c['mobileNetworkCode']
            cell['lac'] = c['locationAreaCode']
            cell['cid'] = c['cellId']
            normalized_cells.append(cell)

        normalized_wifi = []
        for w in batch['wifiAccessPoints']:
            wifi = {}
            wifi['key'] = w['macAddress']
            wifi['frequency'] = 0
            wifi['channel'] = w['channel']
            wifi['signal'] = w['signalStrength']
            normalized_wifi.append(wifi)

        normalized_batch = {'lat': batch['lat'] / (10**7),
                            'lon': batch['lon'] / (10**7),
                            'time': batch['timestamp'],
                            'accuracy': batch['accuracy'],
                            'altitude': batch['altitude'],
                            'altitude_accuracy': batch['altitude_accuracy'],
                            'radio': batch['radioType'],
                            'cell': normalized_cells,
                            'wifi': normalized_wifi}
        batch_list.append(normalized_batch)

    for i in range(0, len(batch_list), 100):
        insert_measures.delay(
            items=dumps(batch_list[i:i + 100]),
            nickname=nickname,
        )


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
    result = None

    if data['wifiAccessPoints']:
        result = search_wifi_ap(session, data)
        if result is not None:
            heka_client.incr('geosubmit.wifi_hit')
            heka_client.timer_send('geosubmit.accuracy.wifi',
                                   result['accuracy'])
    else:
        result = search_cell_tower(session, data)
        if result is not None:
            heka_client.incr('geosubmit.cell_hit')
            heka_client.timer_send('geosubmit.accuracy.cell',
                                   result['accuracy'])

        if result is None:
            result = search_cell_tower_lac(session, data)
            if result is not None:
                heka_client.incr('geosubmit.cell_lac_hit')
                heka_client.timer_send('geosubmit.accuracy.cell_lac',
                                       result['accuracy'])

    if result is None and request.client_addr:
        result = search_geoip(request.registry.geoip_db,
                              request.client_addr)
        if result is not None:
            heka_client.incr('geosubmit.geoip_hit')
            heka_client.timer_send('geosubmit.accuracy.geoip',
                                   result['accuracy'])

    items = data.get('items', [data])
    nickname = request.headers.get('X-Nickname', u'')
    process_upload(nickname, items)

    if result is None:
        heka_client.incr('geolocate.miss')
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
