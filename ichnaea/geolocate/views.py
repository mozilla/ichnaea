import logging

from cornice import Service

from ichnaea.geolocate.schema import GeoLocateSchema
from ichnaea.views import (
    error_handler,
    MSG_ONE_OF,
)

logger = logging.getLogger('ichnaea')


def geolocate_validator(request):
    if len(request.errors):
        return
    data = request.validated
    cell = data.get('cellTowers', ())
    wifi = data.get('wifiAccessPoints', ())
    if not any(wifi) and not any(cell):
        request.errors.add('body', 'body', MSG_ONE_OF)


geolocate = Service(
    name='geolocate',
    path='/v1/geolocate',
    description="Geolocate yourself.",
)


@geolocate.post(renderer='json', accept="application/json",
                schema=GeoLocateSchema, error_handler=error_handler,
                validators=geolocate_validator)
def geolocate_post(request):
    return {
        "location": {
            "lat": 37.789,
            "lng": -122.389,
        },
        "accuracy": 500.0,
    }
