import datetime
import logging

from colander import iso8601

from ichnaea.decimaljson import dumps
from ichnaea.worker import insert_measures

logger = logging.getLogger('ichnaea')


def submit_request(request):
    measures = []
    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    header_token = request.headers.get('X-Token', '')
    if not (24 <= len(header_token) <= 36):
        # doesn't look like it's a uuid
        header_token = ""
    for measure in request.validated['items']:
        try:
            measure['time'] = iso8601.parse_date(measure['time'])
        except (iso8601.ParseError, TypeError):
            if measure['time']:
                # ignore debug log for empty values
                logger.debug('submit_time_error' + repr(measure['time']))
            measure['time'] = utcnow
        else:
            # don't accept future time values
            if measure['time'] > utcnow:
                measure['time'] = utcnow
        if header_token:
            measure['token'] = header_token
        measures.append(dumps(measure))

    insert_measures(measures, db_instance=request.database)
