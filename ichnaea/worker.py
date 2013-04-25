from ichnaea.db import Measure, RADIO_TYPE
from ichnaea.renderer import dump_decimal_json, loads_decimal_json
from ichnaea.db import MeasureDB


def add_measure(request):
    if request.registry.settings.get('async'):
        return push_measure(request)
    return _add_measure(request.validated,
                        db_instance=request.measuredb)


def _get_db(sqluri):
    # XXX keep the connector in a thread locals
    return MeasureDB(sqluri)


def _add_measure(data, db_instance=None, sqluri=None):
    if db_instance is None:
        db_instance = _get_db(sqluri)

    if isinstance(data, basestring):
        data = loads_decimal_json(data)

    session = db_instance.session()
    measure = Measure()
    measure.lat = int(data['lat'] * 1000000)
    measure.lon = int(data['lon'] * 1000000)
    if data.get('cell'):
        measure.radio = RADIO_TYPE.get(data['radio'], 0)
        measure.cell = dump_decimal_json(data['cell'])
    if data.get('wifi'):
        measure.wifi = dump_decimal_json(data['wifi'])
    session.add(measure)
    session.commit()


def push_measure(request):
    data = dump_decimal_json(request.validated)
    request.queue.enqueue('ichnaea.worker:_add_measure', data=data,
                          sqluri=request.measuredb.sqluri)
