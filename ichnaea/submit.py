import datetime
import logging

from colander import iso8601

from ichnaea.decimaljson import dumps
from ichnaea.worker import insert_measures

logger = logging.getLogger('ichnaea')


def submit_request(request):
    logger.debug('submit' + repr(request.validated))
    measures = []
    for measure in request.validated['items']:
        try:
            measure['time'] = iso8601.parse_date(measure['time'])
        except (iso8601.ParseError, TypeError):
            measure['time'] = datetime.datetime.utcnow()
        measures.append(dumps(measure))

    insert_measures(measures, db_instance=request.database)
