import csv
from cStringIO import StringIO
import datetime
from datetime import timedelta
from operator import itemgetter

from sqlalchemy import func
from sqlalchemy.sql.expression import text

from ichnaea.content.models import (
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
        stat_key = STAT_TYPE[name]
        try:
            result[name] = stats[stat_key]
        except KeyError:
            # no stats entry available, maybe closely after midnight
            # and task hasn't run yet, take latest value
            row = session.query(Stat.value).filter(
                Stat.key == stat_key).order_by(
                Stat.time.desc()).limit(1).first()
            if row is not None:
                result[name] = row[0]
            else:
                result[name] = 0
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


def map_world_csv(session):
    select = text("select distinct round(lat / 1000) as lat1, "
                  "round(lon / 1000) as lon1 from mapstat")
    result = session.execute(select)
    rows = StringIO()
    csvwriter = csv.writer(rows)
    csvwriter.writerow(('lat', 'lon'))
    for lat, lon in result.fetchall():
        csvwriter.writerow((int(lat) / 10.0, int(lon) / 10.0))
    return rows.getvalue()
