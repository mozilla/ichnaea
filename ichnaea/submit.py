import datetime
import threading

from ichnaea.decimaljson import dumps
from ichnaea.queue import TimedQueue
from ichnaea.worker import add_measures, push_measures

_LOCK = threading.RLock()
_BATCH = TimedQueue()


def submit_request(request):
    # options
    settings = request.registry.settings
    async = settings.get('async', False)
    batch_size = settings['batch_size']
    batch_age = settings['batch_age']

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

    if async:
        push_measures(request, measures)
    else:
        add_measures(measures, db_instance=request.measuredb)
