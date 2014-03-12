from collections import defaultdict
from sqlalchemy import text
from ichnaea.tasks import DatabaseTask, backfill_cell_location_update
from ichnaea.worker import celery
from ichnaea.geocalc import distance

NEAREST_DISTANCE = 1.0  # Distance in kilometers between towers with no
                        # LAC/CID and towers with known LAC/CID


@celery.task(base=DatabaseTask, bind=True)
def do_backfill(self):
    """
    Find all cell (mcc, mnc, psc) 3-tuples that are missing lac,
    cid and spin up celery tasks to update cells.
    """
    with self.db_session() as session:
        stmt = text("""
                select
                    radio, mcc, mnc, psc
                from
                    cell_measure
                where
                    (mcc != -1 and mnc != -1) and
                    (lac = -1 or cid = -1) and
                    (psc != -1)
                group by
                    radio, mcc, mnc, psc
                """)
        for row in session.execute(stmt):
            update_tower.delay(row['radio'], row['mcc'],
                               row['mnc'], row['psc'])


@celery.task(base=DatabaseTask, bind=True)
def update_tower(self, radio, mcc, mnc, psc):
    rows_updated = 0
    with self.db_session() as session:
        centroids = compute_matching_towers(session, radio, mcc, mnc, psc)

        if centroids == []:
            return

        tower_proxy = compute_missing_towers(session, radio, mcc, mnc, psc)

        new_cell_measures = defaultdict(set)
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
                    lac = :lac,
                    cid = :cid
                where
                  id = :id
                """).bindparams(lac=lac, cid=cid, id=missing_tower['id'])

                new_cell_measures[tower_tuple].add(missing_tower['id'])

                result_proxy = session.execute(stmt)
                rows_updated += result_proxy.rowcount
        session.commit()

        # convert new_cell_measures to a JSON friendly representation
        task_arguments = []
        for k, v in new_cell_measures.items():
            task_arguments.append((k, list(v)))

        # Update the cell tower locations with the newly backfilled
        # measurements now
        backfill_cell_location_update.delay(task_arguments)

    return rows_updated


def compute_matching_towers(session, radio, mcc, mnc, psc):
    """
    Finds the closest matching cell based on mcc, mnc, psc and
    lat/long. If no cell can be found to match within 1km, then we
    return None.
    """
    stmt = text("""
    select
        lat, lon, mcc, mnc, lac, cid, psc
    from
        cell
    where
        radio = :radio and
        mcc = :mcc and
        mnc = :mnc and
        psc = :psc and
        lac != -1 and
        cid != -1
    """).bindparams(radio=radio, mcc=mcc, mnc=mnc, psc=psc)
    row_proxy = session.execute(stmt)
    return [dict(r) for r in row_proxy]


def _nearest_tower(missing_lat, missing_lon, centroids):
    """
    We just need the closest cell, so we can approximate
    using the haversine formula.
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


def compute_missing_towers(session, radio, mcc, mnc, psc):
    stmt = text("""
    select
        id, lat, lon
    from
        cell_measure
    where
        radio = :radio and
        mcc = :mcc and
        mnc = :mnc and
        psc = :psc and
        (lac = -1 or
        cid = -1)
    """).bindparams(radio=radio, mcc=mcc, mnc=mnc, psc=psc)
    return session.execute(stmt)
