import csv
from cStringIO import StringIO

from ichnaea.db import Measure


def map_stats_request(request):
    session = request.database.session()
    query = session.query(Measure.lat, Measure.lon)
    rows = StringIO()
    csvwriter = csv.writer(rows)
    csvwriter.writerow(('lat', 'lon'))
    for lat, lon in query:
        csvwriter.writerow(((lat // 10000) / 1000.0, (lon // 10000) / 1000.0))
    return rows.getvalue()
