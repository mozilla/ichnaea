import csv
from cStringIO import StringIO
import datetime
from datetime import timedelta
import math

from sqlalchemy.sql.expression import text

from ichnaea.db import (
    Score,
    Stat,
    STAT_TYPE,
    User,
)


def global_stats(session):
    today = datetime.datetime.utcnow().date()
    yesterday = today - timedelta(1)
    names = ('location', 'cell', 'wifi', 'unique_cell', 'unique_wifi')
    stat_keys = [STAT_TYPE[name] for name in names]
    rows = session.query(Stat.key, Stat.value).filter(
        Stat.key.in_(stat_keys)).filter(
        Stat.time == yesterday).group_by(Stat.key)

    stats = {}
    for row in rows.all():
        if row[1]:
            stats[row[0]] = int(row[1])

    result = {}
    for name in names:
        result[name] = stats.get(STAT_TYPE[name], 0)
    return result


def histogram(session, name):
    today = datetime.datetime.utcnow().date()
    thirty_days = today - timedelta(days=30)
    stat_key = STAT_TYPE[name]
    rows = session.query(Stat.time, Stat.value).filter(
        Stat.key == stat_key).filter(
        Stat.time >= thirty_days).filter(
        Stat.time < today).order_by(
        Stat.time
    )
    result = []
    for day, num in rows.all():
        if isinstance(day, datetime.date):  # pragma: no cover
            day = day.strftime('%Y-%m-%d')
        result.append({'day': day, 'num': num})
    return result


def leaders(session):
    result = []
    score_rows = session.query(
        Score.userid, Score.value).order_by(Score.value.desc()).all()
    userids = [s[0] for s in score_rows]
    if not userids:
        return []
    user_rows = session.query(User).filter(User.id.in_(userids)).all()
    users = {}
    for user in user_rows:
        users[user.id] = user.nickname

    for userid, value in score_rows:
        nickname = users.get(userid, 'anonymous')
        result.append(
            {'nickname': nickname, 'num': value})
    return result


def map_csv(session):
    select = text("select round(lat / 10000) as lat1, "
                  "round(lon / 10000) as lon1, count(*) as num "
                  "from measure group by lat1, lon1 having num > 2 "
                  "order by lat1, lon1")
    result = session.execute(select)
    rows = StringIO()
    csvwriter = csv.writer(rows)
    csvwriter.writerow(('lat', 'lon', 'value'))
    for lat, lon, num in result.fetchall():
        # use a logarithmic scale to give lesser used regions a chance
        num = int(math.ceil(math.log10(num)))
        csvwriter.writerow((int(lat) / 1000.0, int(lon) / 1000.0, num))
    return rows.getvalue()
