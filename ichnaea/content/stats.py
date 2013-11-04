import csv
from cStringIO import StringIO
import datetime
from datetime import timedelta
from operator import itemgetter

from sqlalchemy import select, func
from sqlalchemy.dialects.mysql import INTEGER as Integer
from sqlalchemy.sql.expression import text

from ichnaea.content.models import (
    MapStat,
    Score,
    SCORE_TYPE,
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
        Score.userid, func.sum(Score.value)).filter(
        Score.key == SCORE_TYPE['location']).group_by(
        Score.userid, Score.key).all()
    # sort descending by value
    score_rows.sort(key=itemgetter(1), reverse=True)
    userids = [s[0] for s in score_rows]
    if not userids:
        return []
    user_rows = session.query(User).filter(User.id.in_(userids)).all()
    users = {}
    for user in user_rows:
        users[user.id] = user.nickname

    for userid, value in score_rows:
        nickname = users.get(userid, 'anonymous')
        if len(nickname) > 30:
            nickname = nickname[:30] + u'...'
        result.append(
            {'nickname': nickname, 'num': int(value)})
    return result


def map_csv(session):
    # use a logarithmic scale to give lesser used regions a chance
    query = select(
        columns=(MapStat.lat, MapStat.lon,
                 func.cast(func.ceil(func.log10(MapStat.value)), Integer)),
        whereclause=MapStat.value >= 20)
    result = session.execute(query).fetchall()
    rows = StringIO()
    csvwriter = csv.writer(rows)
    csvwriter.writerow(('lat', 'lon', 'value'))
    for lat, lon, value in result:
        csvwriter.writerow((lat / 1000.0, lon / 1000.0, value))
    return rows.getvalue()


def map_world_csv(session):
    select = text("select round(lat / 20) as lat1, "
                  "round(lon / 20) as lon1, count(*) as value "
                  "from mapstat group by lat1, lon1 "
                  "order by lat1, lon1")
    result = session.execute(select)
    rows = StringIO()
    csvwriter = csv.writer(rows)
    csvwriter.writerow(('lat', 'lon', 'value'))
    for lat, lon, value in result.fetchall():
        csvwriter.writerow((int(lat) / 50.0, int(lon) / 50.0, int(value)))
    return rows.getvalue()
