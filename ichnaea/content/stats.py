import csv
from cStringIO import StringIO
import datetime
from datetime import timedelta
import math

from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy.sql.expression import text

from ichnaea.db import (
    CellMeasure,
    Measure,
    Score,
    Stat,
    STAT_TYPE,
    User,
    WifiMeasure,
)


def global_stats(session):
    result = {}
    result['location'] = session.query(func.count(Measure.id)).first()[0]
    result['cell'] = session.query(func.count(CellMeasure.id)).first()[0]
    result['unique-cell'] = session.query(
        CellMeasure.radio, CellMeasure.mcc, CellMeasure.mnc,
        CellMeasure.lac, CellMeasure.cid).\
        group_by(CellMeasure.radio, CellMeasure.mcc, CellMeasure.mnc,
                 CellMeasure.lac, CellMeasure.cid).count()
    result['wifi'] = session.query(func.count(WifiMeasure.id)).first()[0]
    result['unique-wifi'] = session.query(
        func.count(distinct(WifiMeasure.key))).first()[0]
    return result


def histogram(session):
    today = datetime.datetime.utcnow().date()
    thirty_days = today - timedelta(days=30)
    stat_key = STAT_TYPE['location']
    rows = session.query(Stat.time, Stat.value).filter(
        Stat.key == stat_key).filter(
        Stat.time >= thirty_days).filter(
        Stat.time < today).order_by(
        Stat.time.desc()
    )
    result = []
    total = session.query(func.sum(Stat.value)).filter(
        Stat.key == stat_key).filter(
        Stat.time < today
    )
    total = total.first()[0]
    if total is None:
        total = 0
    else:
        total = int(total)
    # reverse sort data by day, then count down from total
    for day, num in rows.all():
        if isinstance(day, datetime.date):  # pragma: no cover
            day = day.strftime('%Y-%m-%d')
        result.append({'day': day, 'num': total})
        total -= num
    result.reverse()
    return result


def leaders(session):
    result = []
    score_rows = session.query(
        Score.userid, Score.value).order_by(Score.value.desc()).limit(10).all()
    userids = [s[0] for s in score_rows]
    if not userids:
        return []
    user_rows = session.query(User).filter(User.id.in_(userids)).all()
    users = {}
    for user in user_rows:
        users[user.id] = (user.token, user.nickname)

    for userid, value in score_rows:
        token, nickname = users.get(userid, ('', 'anonymous'))
        result.append(
            {'token': token[:8], 'nickname': nickname, 'num': value})
    return result


def map_csv(session):
    select = text("select round(lat / 10000) as lat1, "
                  "round(lon / 10000) as lon1, count(*) as num "
                  "from measure group by lat1, lon1 having num > 10 "
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
