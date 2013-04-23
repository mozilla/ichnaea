from ichnaea.db import Measure
from ichnaea.renderer import dump_decimal_json


def add_measure(request, async=False):
    data = request.validated

    if async:
        push_measure(data)

    session = request.measuredb.session()
    measure = Measure()
    measure.lat = int(data['lat'] * 1000000)
    measure.lon = int(data['lon'] * 1000000)
    if data.get('cell'):
        measure.cell = dump_decimal_json(data['cell'])
    if data.get('wifi'):
        measure.wifi = dump_decimal_json(data['wifi'])
    session.add(measure)
    session.commit()


def push_measure(data):
    raise NotImplementedError()
