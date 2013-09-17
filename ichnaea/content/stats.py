import csv
from cStringIO import StringIO
import datetime
from datetime import timedelta

from sqlalchemy import select, func
from sqlalchemy.dialects.mysql import INTEGER as Integer

from ichnaea.content.models import (
    MapStat,
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
    # use a logarithmic scale to give lesser used regions a chance
    query = select(
        columns=(MapStat.lat, MapStat.lon,
                 func.cast(func.ceil(func.log10(MapStat.value)), Integer)),
        whereclause=MapStat.value >= 2)
    result = session.execute(query).fetchall()
    rows = StringIO()
    csvwriter = csv.writer(rows)
    csvwriter.writerow(('lat', 'lon', 'value'))
    for lat, lon, value in result:
        csvwriter.writerow((lat / 1000.0, lon / 1000.0, value))
    return rows.getvalue()
