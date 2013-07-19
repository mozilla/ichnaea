import csv
from cStringIO import StringIO

from sqlalchemy.sql.expression import text


def map_stats_request(request):
    session = request.database.session()
    select = text("select distinct round(lat / 100000) as lat, "
                  "round(lon / 100000) as lon from measure order by lat, lon")
    result = session.execute(select)
    rows = StringIO()
    csvwriter = csv.writer(rows)
    csvwriter.writerow(('lat', 'lon'))
    for lat, lon in result.fetchall():
        csvwriter.writerow((lat / 100.0, lon / 100.0))
    return rows.getvalue()
