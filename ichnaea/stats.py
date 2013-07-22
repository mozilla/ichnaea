import datetime

from sqlalchemy.sql.expression import text

from ichnaea.db import Measure

MEASURE_HISTOGRAM_MYSQL = """\
select date(time) as day, count(id) as num from measure where
date_sub(curdate(), interval 30 day) <= time and
date(time) <= curdate() group by date(time)"""

MEASURE_HISTOGRAM_SQLITE = """\
select date(time) as day, count(id) as num from measure where
date('now', '-30 days') <= date(time) and
date(time) <= date('now') group by date(time)"""


def stats_request(request):
    session = request.database.session()
    if 'sqlite' in str(session.bind.engine.url):
        query = MEASURE_HISTOGRAM_SQLITE
    else:
        query = MEASURE_HISTOGRAM_MYSQL
    rows = session.execute(text(query))
    result = {'histogram': []}
    for day, num in rows.fetchall():
        if isinstance(day, datetime.date):
            day = day.strftime('%Y-%m-%d')
        result['histogram'].append({'day': day, 'num': num})
    total = session.query(Measure).count()
    result['total'] = total
    return result
