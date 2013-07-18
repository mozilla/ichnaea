import csv
from cStringIO import StringIO

from ichnaea.db import Measure


def map_stats_request(request):
    session = request.database.session()
    query = session.query(Measure.lat, Measure.lon)
    unique = set()
    for lat, lon in query:
        unique.add(((lat // 100000) / 100.0, (lon // 100000) / 100.0))
    rows = StringIO()
    csvwriter = csv.writer(rows)
    csvwriter.writerow(('lat', 'lon'))
    for lat, lon in unique:
        csvwriter.writerow((lat, lon))
    return rows.getvalue()
