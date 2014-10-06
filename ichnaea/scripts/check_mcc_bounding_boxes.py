import json
import sys

import mobile_codes

from ichnaea.app_config import read_config
from ichnaea.db import Database
from ichnaea.geocalc import location_is_in_country

# This script scans the cell table looking for cells located outside the
# bounding box of the country associated with the MCC. It produces geojson
# output.


def main():

    settings = read_config().get_map('ichnaea')
    db = Database(settings['db_slave'])
    session = db.session()

    bad = []

    offset = 0
    count = 10000
    results = True
    while results:
        results = False
        r = session.execute("select id, lat, lon, mcc, mnc, lac, cid, radio, "
                            "total_measures from cell where "
                            "lat is not null and lon is not null and "
                            "mcc not in (1, 260) "
                            "order by id limit %d offset %d" %
                            (count, offset))
        offset += count
        for row in r:
            results = True
            (id, lat, lon, mcc, mnc, lac, cid, radio, total_measures) = row
            ccs = [c.alpha2 for c in mobile_codes.mcc(str(mcc))]
            if not any([location_is_in_country(lat, lon, c, 1) for c in ccs]):
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
