import json
import sys

import mobile_codes

from ichnaea import config
from ichnaea.db import Database
from ichnaea.geocalc import location_is_in_country
from ichnaea.models import to_degrees

# This script scans the cell table looking for cells located outside the
# bounding box of the country associated with the MCC. It produces geojson
# output.


def main():

    settings = config().get_map('ichnaea')
    db = Database(settings['db_slave'])
    session = db.session()

    bad = []

    offset = 0
    count = 1000
    results = True
    while results:
        results = False
        r = session.execute("select id, lat, lon, mcc, mnc, lac, cid, radio, "
                            + "total_measures from cell limit %d offset %d" %
                            (count, offset))
        offset += count
        for row in r:
            results = True
            (id, lat, lon, mcc, mnc, lac, cid, radio, total_measures) = row
            if not lat or not lon or not id or not mcc:
                continue
            lat = to_degrees(lat)
            lon = to_degrees(lon)
            ccs = [c.alpha2 for c in mobile_codes.mcc(str(mcc))]
            if not any([location_is_in_country(lat, lon, c, 1) for c in ccs]):
                if mcc == 260 or mcc == 1:
                    continue
                if ccs:
                    s = ",".join(ccs)
                else:
                    continue
                bad.append(dict(
                    type='Feature',
                    properties=dict(
                        mcc=mcc,
                        mnc=mnc,
                        lac=lac,
                        cid=cid,
                        radio=radio,
                        total_measures=total_measures,
                        countries=s),
                    geometry=dict(
                        type='Point',
                        coordinates=[lon, lat])))

    json.dump(dict(type='FeatureCollection',
                   features=bad),
              sys.stdout,
              indent=True)

if __name__ == "__main__":
    main()
