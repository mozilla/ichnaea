from functools import wraps

from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden
from redis import ConnectionError

from ichnaea.customjson import dumps
from ichnaea.models.api import ApiKey
from ichnaea.service.error import DAILY_LIMIT
from ichnaea import util

INVALID_API_KEY = {
    'error': {
        'errors': [{
            'domain': 'usageLimits',
            'reason': 'keyInvalid',
            'message': 'Missing or invalid API key.',
        }],
        'code': 400,
        'message': 'Invalid API key',
    }
}
INVALID_API_KEY = dumps(INVALID_API_KEY)


def invalid_api_key_response():
    result = HTTPBadRequest()
    result.content_type = 'application/json'
    result.body = INVALID_API_KEY
    return result


def rate_limit(redis_client, api_key, maxreq=0, expire=86400):
    if not maxreq:
        return False

    dstamp = util.utcnow().strftime('%Y%m%d')
    key = 'apilimit:%s:%s' % (api_key, dstamp)

    try:
        current = redis_client.get(key)
        if current is None or int(current) < maxreq:
            with redis_client.pipeline() as pipe:
                pipe.incr(key, 1)
                pipe.expire(key, expire)  # expire key after 24 hours
                pipe.execute()
            return False
    except ConnectionError:  # pragma: no cover
        # If we cannot connect to Redis, disable rate limitation.
        return None
    return True


def check_api_key(func_name, error_on_invalidkey=True):
    def c(func):
        @wraps(func)
        def closure(request, *args, **kwargs):
            raven_client = request.registry.raven_client
            stats_client = request.registry.stats_client

            api_key = None
            api_key_text = request.GET.get('key', None)

            if api_key_text is None:
                stats_client.incr('%s.no_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()
            try:
                api_key = ApiKey.getkey(request.db_ro_session, api_key_text)
            except Exception:  # pragma: no cover
                # if we cannot connect to backend DB, skip api key check
                raven_client.captureException()
                stats_client.incr('%s.dbfailure_skip_api_key' % func_name)

            if api_key is not None:
                stats_client.incr('%s.api_key.%s' % (func_name, api_key.name))
                should_limit = rate_limit(request.registry.redis_client,
                                          api_key_text, maxreq=api_key.maxreq)
                if should_limit:
                    response = HTTPForbidden()
                    response.content_type = 'application/json'
                    response.body = DAILY_LIMIT
                    return response
                elif should_limit is None:  # pragma: no cover
                    # We couldn't connect to Redis
                    stats_client.incr('%s.redisfailure_skip_limit' % func_name)
            else:
                if api_key_text is not None:
                    stats_client.incr('%s.unknown_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()

            # If we failed to look up an ApiKey, create an empty one
            # rather than passing None through
            api_key = api_key or ApiKey(valid_key=None)

            return func(request, api_key, *args, **kwargs)
        return closure
    return c


def prepare_search_data(request_data, client_addr=None):
    """
    Transform a geolocate API dictionary to an equivalent search API
    dictionary.
    """
    search_data = {
        'geoip': client_addr,
        'cell': [],
        'wifi': [],
    }

    if request_data:
        if 'cellTowers' in request_data:
            for cell in request_data['cellTowers']:
                new_cell = {
                    'mcc': cell['mobileCountryCode'],
                    'mnc': cell['mobileNetworkCode'],
                    'lac': cell['locationAreaCode'],
                    'cid': cell['cellId'],
                }
                # Map a per-cell radioType to our internal radio name
                if 'radioType' in cell and cell['radioType']:
                    new_cell['radio'] = cell['radioType']
                # If a radio field is populated in any one of the cells in
                # cellTowers, this is a buggy geolocate call from FirefoxOS.
                # Just pass on the radio field, as long as it's non-empty.
                elif 'radio' in cell and cell['radio']:
                    new_cell['radio'] = cell['radio']
                # If neither could be found, fall back to top-level
                # radioType field
                if 'radio' not in new_cell:
                    new_cell['radio'] = request_data.get('radioType', None)
                search_data['cell'].append(new_cell)

        if 'wifiAccessPoints' in request_data:
            for wifi in request_data['wifiAccessPoints']:
                new_wifi = {
                    'key': wifi['macAddress'],
                    'signal': wifi['signalStrength'],
                }
                search_data['wifi'].append(new_wifi)

    return search_data
