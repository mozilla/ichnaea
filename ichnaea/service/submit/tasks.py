from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ichnaea.models import (
    Cell,
    CellMeasure,
    Measure,
    RADIO_TYPE,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.decimaljson import (
    decode_datetime,
    encode_datetime,
    loads,
)
from ichnaea.tasks import DatabaseTask
from ichnaea.worker import celery

from ichnaea.service.submit.utils import process_score

sql_null = None  # avoid pep8 warning


def create_cell_measure(measure_data, entry):
    return CellMeasure(
        measure_id=measure_data['id'],
        created=decode_datetime(measure_data.get('created', '')),
        lat=measure_data['lat'],
        lon=measure_data['lon'],
        time=decode_datetime(measure_data.get('time', '')),
        accuracy=measure_data.get('accuracy', 0),
        altitude=measure_data.get('altitude', 0),
        altitude_accuracy=measure_data.get('altitude_accuracy', 0),
        mcc=entry['mcc'],
        mnc=entry['mnc'],
        lac=entry.get('lac', 0),
        cid=entry.get('cid', 0),
        psc=entry.get('psc', 0),
        asu=entry.get('asu', 0),
        signal=entry.get('signal', 0),
        ta=entry.get('ta', 0),
    )


def update_cell_measure_count(measure, session, userid=None):
    if (measure.radio == -1 or measure.lac == 0 or measure.cid == 0):
        # only update data for complete records
        return

    # do we already know about these cells?
    query = session.query(Cell).filter(
        Cell.radio == measure.radio).filter(
        Cell.mcc == measure.mcc).filter(
        Cell.mnc == measure.mnc).filter(
        Cell.lac == measure.lac).filter(
        Cell.cid == measure.cid
    )
    cell = query.first()
    new_cell = 0
    if cell:
        if isinstance(cell.new_measures, (int, long)):
            cell.new_measures = Cell.new_measures + 1
        else:
            # already a sql expression
            cell.new_measures += 1
        if isinstance(cell.total_measures, (int, long)):
            if cell.total_measures < 5:
                # count cells as new until they show up in the search
                new_cell += 1
            cell.total_measures = Cell.total_measures + 1
        else:
            # already a sql expression
            cell.total_measures += 1
            if cell.total_measures.right.value < 5:
                # count cells as new until they show up in the search
                new_cell += 1
    else:
        cell = Cell(radio=measure.radio, mcc=measure.mcc, mnc=measure.mnc,
                    lac=measure.lac, cid=measure.cid,
                    new_measures=1, total_measures=1)
        new_cell += 1
        session.add(cell)
    if userid is not None and new_cell > 0:
        # update user score
        process_score(userid, new_cell, session, key='new_cell')


@celery.task(base=DatabaseTask, ignore_result=True)
def schedule_cell_cleanup(lower, upper, batch=100):
    with schedule_cell_cleanup.db_session() as session:
        stmt = text("select measure.id from measure left join cell_measure "
                    "on measure.id = cell_measure.measure_id where "
                    "cell_measure.measure_id is null and "
                    "measure.cell is not null and "
                    "measure.id > %s and measure.id < %s" % (
                        lower, upper))
        ids = session.execute(stmt).fetchall()
        ids = [int(i[0]) for i in ids]
        for i in range(0, len(ids), batch):
            # split list into batch sized chunks
            reprocess_cell_measure.delay(ids[i:i + batch])
        return len(ids)
    return 0


@celery.task(base=DatabaseTask, ignore_result=True)
def reprocess_cell_measure(measure_ids, userid=None):
    measures = []
    try:
        with reprocess_cell_measure.db_session() as session:
            measures = session.query(Measure).filter(
                Measure.id.in_(measure_ids)).filter(
                Measure.cell != sql_null).all()
            for measure in measures:
                measure_data = dict(
                    id=measure.id, created=encode_datetime(measure.created),
                    lat=measure.lat, lon=measure.lon,
                    time=encode_datetime(measure.time),
                    accuracy=measure.accuracy, altitude=measure.altitude,
                    altitude_accuracy=measure.altitude_accuracy,
                    radio=measure.radio,
                )
                # adds data to this session
                process_cell_measure(
                    session, measure_data, loads(measure.cell), userid=userid)
            session.commit()
        return len(measures)
    except IntegrityError as exc:  # pragma: no cover
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise reprocess_cell_measure.retry(exc=exc)


def process_cell_measure(session, measure_data, entries, userid=None):
    cell_measures = []
    for entry in entries:
        cell = create_cell_measure(measure_data, entry)
        # use more specific cell type or
        # fall back to less precise measure
        if entry.get('radio'):
            cell.radio = RADIO_TYPE.get(entry['radio'], -1)
        else:
            cell.radio = measure_data['radio']
        update_cell_measure_count(cell, session, userid=userid)
        cell_measures.append(cell)
    session.add_all(cell_measures)
    return cell_measures


@celery.task(base=DatabaseTask, ignore_result=True)
def insert_cell_measure(measure_data, entries, userid=None):
    try:
        cell_measures = []
        with insert_cell_measure.db_session() as session:
            cell_measures = process_cell_measure(
                session, measure_data, entries, userid=userid)
            session.commit()
        return len(cell_measures)
    except IntegrityError as exc:  # pragma: no cover
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise insert_cell_measure.retry(exc=exc)


def convert_frequency(entry):
    freq = entry.pop('frequency', 0)
    # if no explicit channel was given, calculate
    if freq and not entry['channel']:
        if 2411 < freq < 2473:
            # 2.4 GHz band
            entry['channel'] = (freq - 2407) // 5
        elif 5169 < freq < 5826:
            # 5 GHz band
            entry['channel'] = (freq - 5000) // 5


def update_wifi_measure_count(wifi_key, wifis, session, userid=None):
    # side-effect, modifies wifis
    new_wifi = 0
    if wifi_key in wifis:
        wifi = wifis[wifi_key]
        if isinstance(wifi.new_measures, (int, long)):
            wifi.new_measures = Wifi.new_measures + 1
        else:
            # already a sql expression
            wifi.new_measures += 1
        if isinstance(wifi.total_measures, (int, long)):
            if wifi.total_measures < 5:
                # count wifis as new until they show up in the search
                new_wifi += 1
            wifi.total_measures = Wifi.total_measures + 1
        else:
            # already a sql expression
            wifi.total_measures += 1
    else:
        wifis[wifi_key] = wifi = Wifi(
            key=wifi_key, new_measures=1, total_measures=1)
        new_wifi += 1
        session.add(wifi)
    if userid is not None and new_wifi > 0:
        # update user score
        process_score(userid, new_wifi, session, key='new_wifi')


def create_wifi_measure(measure_data, entry):
    return WifiMeasure(
        measure_id=measure_data['id'],
        created=decode_datetime(measure_data.get('created', '')),
        lat=measure_data['lat'],
        lon=measure_data['lon'],
        time=decode_datetime(measure_data.get('time', '')),
        accuracy=measure_data.get('accuracy', 0),
        altitude=measure_data.get('altitude', 0),
        altitude_accuracy=measure_data.get('altitude_accuracy', 0),
        id=entry.get('id', None),
        key=entry['key'],
        channel=entry.get('channel', 0),
        signal=entry.get('signal', 0),
    )


@celery.task(base=DatabaseTask, ignore_result=True)
def reprocess_wifi_measure(measure_ids, userid=None):
    measures = []
    try:
        with reprocess_wifi_measure.db_session() as session:
            measures = session.query(Measure).filter(
                Measure.id.in_(measure_ids)).filter(
                Measure.wifi != sql_null).all()
            for measure in measures:
                measure_data = dict(
                    id=measure.id, created=encode_datetime(measure.created),
                    lat=measure.lat, lon=measure.lon,
                    time=encode_datetime(measure.time),
                    accuracy=measure.accuracy, altitude=measure.altitude,
                    altitude_accuracy=measure.altitude_accuracy,
                    radio=measure.radio,
                )
                insert_wifi_measure.delay(
                    measure_data, loads(measure.wifi), userid=userid)
        return len(measures)
    except IntegrityError as exc:  # pragma: no cover
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise reprocess_wifi_measure.retry(exc=exc)


@celery.task(base=DatabaseTask, ignore_result=True)
def insert_wifi_measure(measure_data, entries, userid=None):
    wifi_measures = []
    wifi_keys = set([e['key'] for e in entries])
    try:
        with insert_wifi_measure.db_session() as session:
            # did we get measures for blacklisted wifis?
            blacked = session.query(WifiBlacklist.key).filter(
                WifiBlacklist.key.in_(wifi_keys)).all()
            blacked = set([b[0] for b in blacked])
            # do we already know about these wifis?
            wifis = session.query(Wifi.key, Wifi).filter(
                Wifi.key.in_(wifi_keys))
            wifis = dict(wifis.all())
            for entry in entries:
                wifi_key = entry['key']
                # skip blacklisted wifi AP's
                if wifi_key in blacked:
                    continue
                # convert frequency into channel numbers and remove frequency
                convert_frequency(entry)
                wifi_measures.append(create_wifi_measure(measure_data, entry))
                # update new/total measure counts
                update_wifi_measure_count(
                    wifi_key, wifis, session, userid=userid)

            session.add_all(wifi_measures)
            session.commit()
        return len(wifi_measures)
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise insert_wifi_measure.retry(exc=exc)
