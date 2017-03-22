from calendar import timegm
from datetime import date, timedelta
from operator import itemgetter

import genc
from sqlalchemy import func, select

from ichnaea.models.content import (
    RegionStat,
    Stat,
    StatKey,
)
from ichnaea import util

transliterate_mapping = {
    231: 'c', 244: 'o', 8217: "'",
}


def transliterate(string):
    # optimize for the common case of ascii-only
    non_ascii = any([ord(char) > 127 for char in string])
    if not non_ascii:
        return string

    result = []
    for char in string:
        if ord(char) > 127:
            result.append(transliterate_mapping.get(ord(char), char))
        else:
            result.append(char)

    return ''.join(result)


def global_stats(session):
    today = util.utcnow().date()
    stat_keys = (
        StatKey.blue,
        StatKey.cell,
        StatKey.wifi,
        StatKey.unique_blue,
        StatKey.unique_cell,
        StatKey.unique_wifi,
    )

    columns = Stat.__table__.c
    rows = session.execute(
        select([columns.key, columns.value])
        .where(columns.key.in_(stat_keys))
        .where(columns.time == today)
    ).fetchall()

    stats = {}
    for row in rows:
        if row.value:
            stats[row.key] = int(row.value)

    result = {}
    for stat_key in stat_keys:
        name = stat_key.name
        try:
            result[name] = stats[stat_key]
        except KeyError:
            # no stats entry available, maybe closely after midnight
            # and task hasn't run yet, take latest value
            row = session.execute(
                select([columns.value])
                .where(columns.key == stat_key)
                .order_by(columns.time.desc())
                .limit(1)
            ).fetchone()
            if row is not None:
                result[name] = row.value
            else:
                result[name] = 0

    for k, v in result.items():
        # show as millions
        result[k] = '%.2f' % ((v // 10000) / 100.0)

    return result


def histogram(session, stat_key, days=365):
    today = util.utcnow().date()
    start = today - timedelta(days=days)
    columns = Stat.__table__.c
    month_key = [func.year(columns.time), func.month(columns.time)]
    rows = session.execute(
        select(month_key + [func.max(columns.value)])
        .where(columns.key == stat_key)
        .where(columns.time >= start)
        .group_by(*month_key)
        .order_by(*month_key)
    ).fetchall()
    result = []
    for year, month, num in rows:
        # Use the first of the month to graph the value
        # for the entire month.
        day = timegm(date(year, month, 1).timetuple()) * 1000
        result.append([day, num])
    return [result]


def regions(session):
    columns = RegionStat.__table__.c
    rows = session.execute(
        select([columns.region, columns.gsm, columns.wcdma, columns.lte,
                columns.blue, columns.wifi])
    ).fetchall()

    regions = {}
    for row in rows:
        code = row.region
        name = genc.region_by_alpha2(code).name
        gsm = int(row.gsm or 0)
        wcdma = int(row.wcdma or 0)
        lte = int(row.lte or 0)
        cell = sum((gsm, wcdma, lte))
        regions[code] = {
            'code': code,
            'name': name,
            'order': transliterate(name[:10]).lower(),
            'gsm': gsm,
            'wcdma': wcdma,
            'lte': lte,
            'cell': cell,
            'blue': int(row.blue or 0),
            'wifi': int(row.wifi or 0),
        }
    return sorted(regions.values(), key=itemgetter('cell'), reverse=True)
