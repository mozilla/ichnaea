from sqlalchemy import text
from ichnaea.tasks import DatabaseTask, backfill_cell_location_update
from ichnaea.worker import celery
from ichnaea.geocalc import distance

NEAREST_DISTANCE = 10.0  # Distance in kilometers between towers with no
                         # LAC/CID and towers with known LAC/CId


@celery.task(base=DatabaseTask, bind=True)
def do_backfill(self):
    """
    * Find all tower (mcc, mnc, psc) 3-tuples that are missing lac,
    cid and fill them into the cell_backfill table

    *. For each tower that matches mcc, mnc, psc and has (lac or
    cid=-1, iterate

        * initialize a cache of matching towers for (mcc, mnc, psc)
        * compute matching towers

    """
    with self.db_session() as session:
        stmt = text("""
                select
                    mcc, mnc, psc, radio
                from
                    cell_measure
                where
                    (mcc != -1 and mnc != -1) and
                    (lac = -1 or cid = -1) and
                    (psc != -1)
                group by
                    mcc, mnc, psc, radio
                """)
        for row in session.execute(stmt):
            update_tower.delay(row['mcc'], row['mnc'], row['psc'], row['radio'])


@celery.task(base=DatabaseTask, bind=True)
def update_tower(self, mcc, mnc, psc, radio):
    rows_updated = 0
    with self.db_session() as session:
        centroids = compute_matching_towers(session, mcc, mnc, psc, radio)

        if centroids == []:
            return

        tower_proxy = compute_missing_towers(session, mcc, mnc, psc, radio)

        new_cell_measures = {}
        for missing_tower in tower_proxy:
            matching_tower = _nearest_tower(missing_tower['lat'],
                                            missing_tower['lon'],
                                            centroids)
            if matching_tower:
                lac = matching_tower['pt']['lac']
                cid = matching_tower['pt']['cid']
                tower_tuple = (radio, mcc, mnc, lac, cid)

                stmt = text("""
                update
                    cell_measure
                set
                    lac = %(lac)d,
                    cid = %(cid)d
                where
                  id = %(id)d
                """ % {'id': missing_tower['id'],
                       'lac': lac,
                       'cid': cid})

                if tower_tuple not in new_cell_measures:
                    new_cell_measures[tower_tuple] = set()

                new_cell_measures[tower_tuple].add(missing_tower['id'])

                result_proxy = session.execute(stmt)
                rows_updated += result_proxy.rowcount
        session.commit()

        # Update the cell tower locations with the newly backfilled
        # measurements now
        backfill_cell_location_update.delay(new_cell_measures)

    return rows_updated


def compute_matching_towers(session, mcc, mnc, psc, radio, accuracy=35):
    """
    Finds the closest matching tower based on mcc, mnc, psc, and
    lat/long.  If no tower can be found to match within 1km, then we
    return None.
    """
    stmt = text("""
    select
        (min_lat + max_lat)/2 as lat,
        (min_lon + max_lon)/2 as lon,
        mcc, mnc, lac, cid, psc, rowcount
    from
    (
    select
        min(lat) as min_lat,
        max(lat) as max_lat,
        min(lon) as min_lon,
        max(lon) as max_lon,
        mcc, mnc, lac, cid, psc,
        count(*) as rowcount
    from cell_measure
    where
        mcc = %(mcc)d and
        mnc = %(mnc)d and
        psc = %(psc)d and
        radio = %(radio)d and
        accuracy <= %(accuracy)d and
        lac != -1 and
        cid != -1
    group by
        mcc, mnc, lac, cid
    order by created desc
    ) as data
    """ % {'mcc': mcc,
           'mnc': mnc,
           'psc': psc,
           'accuracy': accuracy,
           'radio': radio}
    )
    row_proxy = session.execute(stmt)
    return [dict(r) for r in row_proxy]


def _nearest_tower(missing_lat, missing_lon, centroids):
    """
    We just need the closest tower, so we can approximate
    using the haversine formula
    """
    FLOAT_CONST = 10000000.0
    lat1 = missing_lat / FLOAT_CONST
    lon1 = missing_lon / FLOAT_CONST

    min_dist = None
    for pt in centroids:
        lat2 = float(pt['lat']) / FLOAT_CONST
        lon2 = float(pt['lon']) / FLOAT_CONST
        dist = distance(lat1, lon1, lat2, lon2)
        if min_dist is None or min_dist['dist'] > dist:
            min_dist = {'dist': dist, 'pt': pt}
    if min_dist['dist'] <= NEAREST_DISTANCE:
        return min_dist


def compute_missing_towers(session, mcc, mnc, psc, radio):
    stmt = text("""
    select
        id,
        lat,
        lon
    from
        cell_measure
    where
        mcc = %(mcc)d and
        mnc = %(mnc)d and
        psc = %(psc)d and
        radio = %(radio)d and
        (lac = -1 or
        cid = -1)
    """ % {'mcc': mcc,
           'mnc': mnc,
           'psc': psc,
           'radio': radio})
    return session.execute(stmt)
