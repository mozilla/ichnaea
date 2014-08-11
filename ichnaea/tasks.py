from collections import defaultdict
from datetime import timedelta

from ichnaea.async.task import DatabaseTask
from ichnaea.geocalc import distance, centroid, range_to_points
from ichnaea.models import (
    CELLID_LAC,
    Cell,
    CellBlacklist,
    CellKey,
    CellMeasure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
    join_cellkey,
    join_wifikey,
    to_cellkey,
    to_wifikey,
)
from ichnaea.stats import get_stats_client
from ichnaea import util
from ichnaea.worker import celery

WIFI_MAX_DIST_KM = 5
CELL_MAX_DIST_KM = 150


def daily_task_days(ago):
    today = util.utcnow().date()
    day = today - timedelta(days=ago)
    max_day = day + timedelta(days=1)
    return day, max_day


@celery.task(base=DatabaseTask, bind=True)
def remove_wifi(self, wifi_keys):
    wifi_keys = set([w['key'] for w in wifi_keys])
    try:
        with self.db_session() as session:
            query = session.query(Wifi).filter(
                Wifi.key.in_(wifi_keys))
            wifis = query.delete(synchronize_session=False)
            session.commit()
        return wifis
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def remove_cell(self, cell_keys):
    cells_removed = 0
    try:
        with self.db_session() as session:
            changed_lacs = set()

            for k in cell_keys:
                key = to_cellkey(k)
                query = session.query(Cell).filter(*join_cellkey(Cell, key))
                cells_removed += query.delete()
                changed_lacs.add(key._replace(cid=CELLID_LAC))

            for key in changed_lacs:
                # Either schedule an update to the enclosing LAC or, if
                # we just removed the last cell in the LAC, remove the LAC
                # entirely.
                query = session.query(Cell).filter(
                    Cell.radio == key.radio,
                    Cell.mcc == key.mcc,
                    Cell.mnc == key.mnc,
                    Cell.lac == key.lac,
                    Cell.cid != CELLID_LAC)
                n = query.count()

                query = session.query(Cell).filter(
                    Cell.radio == key.radio,
                    Cell.mcc == key.mcc,
                    Cell.mnc == key.mnc,
                    Cell.lac == key.lac,
                    Cell.cid == CELLID_LAC)
                if n < 1:
                    query.delete()
                else:
                    lac = query.first()
                    if lac is not None:
                        lac.new_measures += 1

            session.commit()
        return cells_removed
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


def calculate_new_position(station, measures, max_dist_km, backfill=True):
    # Ff backfill is true, we work on older measures for which
    # the new/total counters where never updated.
    # This function returns True if the station was found to be moving.
    length = len(measures)
    latitudes = [w[0] for w in measures]
    longitudes = [w[1] for w in measures]
    new_lat = sum(latitudes) / length
    new_lon = sum(longitudes) / length

    if station.lat and station.lon:
        latitudes.append(station.lat)
        longitudes.append(station.lon)
        existing_station = True
    else:
        station.lat = new_lat
        station.lon = new_lon
        existing_station = False

    # calculate extremes of measures, existing location estimate
    # and existing extreme values
    def extreme(vals, attr, function):
        new = function(vals)
        old = getattr(station, attr, None)
        if old is not None:
            return function(new, old)
        else:
            return new

    min_lat = extreme(latitudes, 'min_lat', min)
    min_lon = extreme(longitudes, 'min_lon', min)
    max_lat = extreme(latitudes, 'max_lat', max)
    max_lon = extreme(longitudes, 'max_lon', max)

    # calculate sphere-distance from opposite corners of
    # bounding box containing current location estimate
    # and new measurements; if too big, station is moving
    box_dist = distance(min_lat, min_lon, max_lat, max_lon)

    if existing_station:

        if box_dist > max_dist_km:
            # Signal a moving station and return early without updating
            # the station since it will be deleted by caller momentarily
            return True

        if backfill:
            new_total = station.total_measures + length
            old_length = station.total_measures
            # update total to account for new measures
            # new counter never got updated to include the measures
            station.total_measures = new_total
        else:
            new_total = station.total_measures
            old_length = new_total - length

        station.lat = ((station.lat * old_length) +
                       (new_lat * length)) / new_total
        station.lon = ((station.lon * old_length) +
                       (new_lon * length)) / new_total

    if not backfill:
        # decrease new counter, total is already correct
        # in the backfill case new counter was never increased
        station.new_measures = station.new_measures - length

    # update max/min lat/lon columns
    station.min_lat = min_lat
    station.min_lon = min_lon
    station.max_lat = max_lat
    station.max_lon = max_lon

    # give radio-range estimate between extreme values and centroid
    ctr = (station.lat, station.lon)
    points = [(min_lat, min_lon),
              (min_lat, max_lon),
              (max_lat, min_lon),
              (max_lat, max_lon)]

    station.range = range_to_points(ctr, points) * 1000.0
    station.modified = util.utcnow()


def update_enclosing_lacs(session, lacs, moving_cells, utcnow):
    moving_cell_ids = set([c.id for c in moving_cells])
    for lac_key, cells in lacs.items():
        if len(set([c.id for c in cells]) - moving_cell_ids) == 0:
            # All new cells are about to be removed, so don't bother
            # updating the lac
            continue
        q = session.query(Cell).filter(*join_cellkey(Cell, lac_key))
        lac = q.first()
        if lac is not None:
            lac.new_measures += 1
        else:
            lac = Cell(
                radio=lac_key.radio,
                mcc=lac_key.mcc,
                mnc=lac_key.mnc,
                lac=lac_key.lac,
                cid=lac_key.cid,
                new_measures=1,
                total_measures=0,
                created=utcnow,
            )
            session.add(lac)


def emit_new_measures_metric(stats_client, session, shortname,
                             model, min_new, max_new):
    q = session.query(model).filter(
        model.new_measures >= min_new,
        model.new_measures < max_new)
    n = q.count()
    stats_client.gauge('task.%s.new_measures_%d_%d' %
                       (shortname, min_new, max_new), n)


@celery.task(base=DatabaseTask, bind=True)
def backfill_cell_location_update(self, new_cell_measures):
    try:
        utcnow = util.utcnow()
        cells = []
        moving_cells = set()
        updated_lacs = defaultdict(list)
        new_cell_measures = dict(new_cell_measures)
        with self.db_session() as session:
            for tower_tuple, cell_measure_ids in new_cell_measures.items():
                query = session.query(Cell).filter(
                    *join_cellkey(Cell, CellKey(*tower_tuple)))
                cells = query.all()

                if not cells:
                    # This case shouldn't actually occur. The
                    # backfill_cell_location_update is only called
                    # when CellMeasure records are matched against
                    # known Cell records.
                    continue

                for cell in cells:
                    measures = session.query(  # NOQA
                        CellMeasure.lat, CellMeasure.lon).filter(
                        CellMeasure.id.in_(cell_measure_ids)).all()

                    if measures:
                        moving = calculate_new_position(
                            cell, measures, CELL_MAX_DIST_KM, backfill=True)
                        if moving:
                            moving_cells.add(cell)

                        updated_lacs[CellKey(cell.radio, cell.mcc,
                                             cell.mnc, cell.lac,
                                             CELLID_LAC)].append(cell)

            if updated_lacs:
                update_enclosing_lacs(session, updated_lacs,
                                      moving_cells, utcnow)

            if moving_cells:
                # some cells found to be moving too much
                blacklist_and_remove_moving_cells(session, moving_cells)

            session.commit()
        return (len(cells), len(moving_cells))
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def cell_location_update(self, min_new=10, max_new=100, batch=10):
    try:
        utcnow = util.utcnow()
        cells = []
        with self.db_session() as session:
            emit_new_measures_metric(self.stats_client, session,
                                     self.shortname, Cell,
                                     min_new, max_new)
            query = session.query(Cell).filter(
                Cell.new_measures >= min_new).filter(
                Cell.new_measures < max_new).filter(
                Cell.cid != CELLID_LAC).limit(batch)
            cells = query.all()
            if not cells:
                return 0
            moving_cells = set()
            updated_lacs = defaultdict(list)
            for cell in cells:
                # skip cells with a missing lac/cid
                # or virtual LAC cells
                if cell.lac == -1 or cell.cid == -1 or \
                   cell.cid == CELLID_LAC:
                    continue

                query = session.query(
                    CellMeasure.lat, CellMeasure.lon, CellMeasure.id).filter(
                    *join_cellkey(CellMeasure, cell))
                # only take the last X new_measures
                query = query.order_by(
                    CellMeasure.created.desc()).limit(
                    cell.new_measures)
                measures = query.all()

                if measures:
                    moving = calculate_new_position(
                        cell, measures, CELL_MAX_DIST_KM, backfill=False)
                    if moving:
                        moving_cells.add(cell)

                    updated_lacs[CellKey(cell.radio, cell.mcc,
                                         cell.mnc, cell.lac,
                                         CELLID_LAC)].append(cell)

            if updated_lacs:
                update_enclosing_lacs(session, updated_lacs,
                                      moving_cells, utcnow)

            if moving_cells:
                # some cells found to be moving too much
                blacklist_and_remove_moving_cells(session, moving_cells)

            session.commit()

        return (len(cells), len(moving_cells))
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


def blacklist_and_remove_moving_stations(session, blacklist_model,
                                         station_type, to_key, join_key,
                                         moving_stations, remove_station):
    moving_keys = []
    utcnow = util.utcnow()
    for station in moving_stations:
        key = to_key(station)
        query = session.query(blacklist_model).filter(
            *join_key(blacklist_model, key))
        b = query.first()
        d = key._asdict()
        moving_keys.append(d)
        if b:
            b.time = utcnow
            b.count += 1
        else:
            b = blacklist_model(**d)
            session.add(b)

    if moving_keys:
        get_stats_client().incr("items.blacklisted.%s_moving" % station_type,
                                len(moving_keys))
        remove_station.delay(moving_keys)


def blacklist_and_remove_moving_wifis(session, moving_wifis):
    blacklist_and_remove_moving_stations(session,
                                         blacklist_model=WifiBlacklist,
                                         station_type="wifi",
                                         to_key=to_wifikey,
                                         join_key=join_wifikey,
                                         moving_stations=moving_wifis,
                                         remove_station=remove_wifi)


def blacklist_and_remove_moving_cells(session, moving_cells):
    blacklist_and_remove_moving_stations(session,
                                         blacklist_model=CellBlacklist,
                                         station_type="cell",
                                         to_key=to_cellkey,
                                         join_key=join_cellkey,
                                         moving_stations=moving_cells,
                                         remove_station=remove_cell)


@celery.task(base=DatabaseTask, bind=True)
def wifi_location_update(self, min_new=10, max_new=100, batch=10):
    try:
        wifis = {}
        with self.db_session() as session:
            emit_new_measures_metric(self.stats_client, session,
                                     self.shortname, Wifi,
                                     min_new, max_new)
            query = session.query(Wifi.key, Wifi).filter(
                Wifi.new_measures >= min_new).filter(
                Wifi.new_measures < max_new).limit(batch)
            wifis = dict(query.all())
            if not wifis:
                return 0
            moving_wifis = set()
            for wifi_key, wifi in wifis.items():
                # only take the last X new_measures
                measures = session.query(
                    WifiMeasure.lat, WifiMeasure.lon).filter(
                    WifiMeasure.key == wifi_key).order_by(
                    WifiMeasure.created.desc()).limit(
                    wifi.new_measures).all()
                if measures:
                    moving = calculate_new_position(
                        wifi, measures, WIFI_MAX_DIST_KM, backfill=False)
                    if moving:
                        moving_wifis.add(wifi)

            if moving_wifis:
                # some wifis found to be moving too much
                blacklist_and_remove_moving_wifis(session, moving_wifis)

            session.commit()
        return (len(wifis), len(moving_wifis))
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def scan_lacs(self, batch=100):
    """
    Find cell LACs that have changed and update the bounding box.

    """
    with self.db_session() as session:
        q = session.query(Cell).filter(
            Cell.cid == CELLID_LAC).filter(
            Cell.new_measures > 0).limit(batch)
        lacs = q.all()
        n = len(lacs)
        for lac in lacs:
            update_lac.delay(lac.radio, lac.mcc,
                             lac.mnc, lac.lac)
        session.commit()
        return n


@celery.task(base=DatabaseTask, bind=True)
def update_lac(self, radio, mcc, mnc, lac):
    try:
        with self.db_session() as session:
            # Select all the cells in this LAC that aren't the virtual
            # cell itself, and derive a bounding box for them.

            q = session.query(Cell).filter(
                Cell.radio == radio).filter(
                Cell.mcc == mcc).filter(
                Cell.mnc == mnc).filter(
                Cell.lac == lac).filter(
                Cell.cid != CELLID_LAC).filter(
                Cell.new_measures == 0).filter(
                Cell.lat.isnot(None)).filter(
                Cell.lon.isnot(None))

            cells = q.all()
            if len(cells) == 0:
                return

            points = [(c.lat, c.lon) for c in cells]
            min_lat = min([c.min_lat for c in cells])
            min_lon = min([c.min_lon for c in cells])
            max_lat = max([c.max_lat for c in cells])
            max_lon = max([c.max_lon for c in cells])

            bbox_points = [(min_lat, min_lon),
                           (min_lat, max_lon),
                           (max_lat, min_lon),
                           (max_lat, max_lon)]

            ctr = centroid(points)
            rng = range_to_points(ctr, bbox_points)

            # switch units back to DB preferred centimicrodegres angle
            # and meters distance.
            ctr_lat = ctr[0]
            ctr_lon = ctr[1]
            rng = int(round(rng * 1000.0))

            # Now create or update the LAC virtual cell

            q = session.query(Cell).filter(
                Cell.radio == radio).filter(
                Cell.mcc == mcc).filter(
                Cell.mnc == mnc).filter(
                Cell.lac == lac).filter(
                Cell.cid == CELLID_LAC)

            lac = q.first()

            if lac is None:
                lac = Cell(radio=radio,
                           mcc=mcc,
                           mnc=mnc,
                           lac=lac,
                           cid=CELLID_LAC,
                           lat=ctr_lat,
                           lon=ctr_lon,
                           range=rng)
                session.add(lac)
            else:
                lac.new_measures = 0
                lac.lat = ctr_lat
                lac.lon = ctr_lon
                lac.range = rng

            session.commit()
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)
