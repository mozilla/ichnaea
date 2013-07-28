import datetime
import logging

from colander import iso8601

from ichnaea.db import User
from ichnaea.decimaljson import dumps
from ichnaea.worker import insert_measures

logger = logging.getLogger('ichnaea')


def submit_request(request):
    session = request.database.session()
    measures = []
    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    header_token = request.headers.get('X-Token', '')
    header_nickname = ''
    if not (24 <= len(header_token) <= 36):
        # doesn't look like it's a uuid
        header_token = ""
    else:
        header_nickname = request.headers.get('X-Nickname', '')
        if (3 <= len(header_nickname) <= 128):
            # automatically create user objects and update nickname
            if isinstance(header_nickname, str):
                header_nickname = header_nickname.decode('utf-8', 'ignore')
            rows = session.query(User).filter(User.token == header_token)
            old = rows.first()
            if old:
                # update nickname
                old.nickname = header_nickname
            else:
                user = User()
                user.token = header_token
                user.nickname = header_nickname
                session.add(user)

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

    insert_measures(measures, session)
    session.commit()
