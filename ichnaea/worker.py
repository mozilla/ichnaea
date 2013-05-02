import threading
import datetime

from colander.iso8601 import parse_date

from ichnaea.db import Measure, RADIO_TYPE
from ichnaea.decimaljson import dumps, loads, to_precise_int
from ichnaea.db import MeasureDB
from ichnaea.queue import TimedQueue


_LOCALS = threading.local()
_LOCALS.dbs = {}
_BATCH_SIZE = 100
_MAX_AGE = datetime.timedelta(seconds=600)
_LOCK = threading.RLock()
_BATCH = TimedQueue(maxsize=_BATCH_SIZE)


def add_measures(request):
    """Adds measures in a queue and dump them to the database when
    a batch is ready.

    In async mode the batch is pushed in redis.
    """
    # options
    settings = request.registry.settings
    batch_size = int(settings.get('batch_size', _BATCH_SIZE))
    batch_age = settings.get('batch_age')
    if batch_age is None:
        batch_age = _MAX_AGE
    else:
        batch_age = datetime.timedelta(seconds=batch_age)

    # data
    measures = []
    for measure in request.validated['items']:
        if measure['time'] is None:
            measure['time'] = datetime.datetime.utcnow()
        measures.append(dumps(measure))

    if batch_size != -1:
        # we are batching in memory
        for measure in measures:
            _BATCH.put(measure)

        # using a lock so only on thread gets to empty the queue
        with _LOCK:
            current_size = _BATCH.qsize()
            batch_ready = _BATCH.age > batch_age or current_size >= batch_size

            if not batch_ready:
                return

            measures = [_BATCH.get() for i in range(current_size)]

    if request.registry.settings.get('async'):
        return push_measures(request, measures)

    return _add_measures(measures, db_instance=request.measuredb)


def _get_db(sqluri):
    if sqluri not in _LOCALS.dbs:
        _LOCALS.dbs[sqluri] = MeasureDB(sqluri)
    return _LOCALS.dbs[sqluri]


def _process_wifi(values):
    # convert frequency into channel numbers
    result = []
    for entry in values:
        # always remove frequency
        freq = entry.pop('frequency')
        # if no explicit channel was given, calculate
        if freq and not entry['channel']:
            if 2411 < freq < 2473:
                # 2.4 GHz band
                entry['channel'] = (freq - 2407) // 5
            elif 5169 < freq < 5826:
                # 5 GHz band
                entry['channel'] = (freq - 5000) // 5
        result.append(entry)
    return result


def _add_measures(measures, db_instance=None, sqluri=None):

    if db_instance is None:
        db_instance = _get_db(sqluri)

    session = db_instance.session()

    for data in measures:
        if isinstance(data, basestring):
            data = loads(data)
        measure = Measure()
        time = data['time']
        if isinstance(time, basestring):
            time = parse_date(time)
        measure.time = time
        measure.lat = to_precise_int(data['lat'])
        measure.lon = to_precise_int(data['lon'])
        measure.accuracy = data['accuracy']
        measure.altitude = data['altitude']
        measure.altitude_accuracy = data['altitude_accuracy']
        if data.get('cell'):
            measure.radio = RADIO_TYPE.get(data['radio'], 0)
            measure.cell = dumps(data['cell'])
        if data.get('wifi'):
            measure.wifi = dumps(_process_wifi(data['wifi']))
        session.add(measure)

    session.commit()


def push_measures(request, measures):
    request.queue.enqueue('ichnaea.worker:_add_measures', measures=measures,
                          sqluri=request.measuredb.sqluri)
