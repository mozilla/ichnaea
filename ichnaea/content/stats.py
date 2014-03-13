from collections import defaultdict
import datetime
from datetime import timedelta
from operator import itemgetter

from mobile_codes import mcc
from sqlalchemy import func

from ichnaea.models import (
    Cell,
    RADIO_TYPE_INVERSE,
)

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
    names = ('cell', 'wifi', 'unique_cell', 'unique_wifi')
    stat_keys = [STAT_TYPE[name] for name in names]
    rows = session.query(Stat.key, Stat.value).filter(
        Stat.key.in_(stat_keys)).filter(
        Stat.time == yesterday)

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

    for k, v in result.items():
        # show as millions
        result[k] = "%.2f" % ((v // 10000) / 100.0)

    return result


def histogram(session, name, days=60):
    today = datetime.datetime.utcnow().date()
    start = today - timedelta(days=days)
    stat_key = STAT_TYPE[name]
    rows = session.query(Stat.time, Stat.value).filter(
        Stat.key == stat_key).filter(
        Stat.time >= start).filter(
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
        if len(nickname) > 24:
            nickname = nickname[:24] + u'...'
        result.append(
            {'nickname': nickname, 'num': int(value)})
    return result


def countries(session):
    # we group by radio, mcc to take advantage of the index
    rows = session.query(Cell.radio, Cell.mcc, func.count(Cell.id)).filter(
        Cell.radio.in_([0, 1, 2, 3])).group_by(Cell.radio, Cell.mcc).all()

    # reverse grouping by mcc, radio
    codes = defaultdict(dict)
    for row in rows:
        codes[row[1]][row[0]] = row[2]

    countries = {}
    for code, item in codes.items():
        try:
            name = mcc(str(code)).name
        except KeyError:
            # we have some bogus networks in the database
            continue
        country = {
            'name': name,
            'total': 0,
            'gsm': 0, 'cdma': 0, 'umts': 0, 'lte': 0,
        }
        for t, v in item.items():
            country[RADIO_TYPE_INVERSE[t]] = int(v)
        country['total'] = int(sum(item.values()))
        if name not in countries:
            countries[name] = country
        else:
            # some countries like the US have multiple mcc codes,
            # we merge them here
            for k, v in country.items():
                if isinstance(v, int):
                    countries[name][k] += v

    return sorted(countries.values(), key=itemgetter('name'))
