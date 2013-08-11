import datetime
from operator import itemgetter

from sqlalchemy import func
from sqlalchemy.sql.expression import text

from ichnaea.db import Measure


def histogram(session):
    query = text("select date(time) as day, count(*) as num from measure "
                 "where date_sub(curdate(), interval 30 day) <= time and "
                 "date(time) <= curdate() group by date(time)")
    rows = session.execute(query)
    result = []
    reverse_rows = sorted(rows.fetchall(), key=itemgetter(0), reverse=True)
    total = session.query(func.count(Measure.id)).first()[0]
    # reverse sort data by day, then count down from total
    for day, num in reverse_rows:
        if isinstance(day, datetime.date):  # pragma: no cover
            day = day.strftime('%Y-%m-%d')
        result.append({'day': day, 'num': total})
        total -= num
    result.reverse()
    return result
