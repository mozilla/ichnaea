from celery.utils.log import get_task_logger
from sqlalchemy.exc import IntegrityError

from ichnaea.models import (
    Cell,
    CellMeasure,
    RADIO_TYPE,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.decimaljson import (
    decode_datetime,
)
from ichnaea.tasks import DatabaseTask
from ichnaea.worker import celery

from ichnaea.service.submit.utils import process_score

logger = get_task_logger(__name__)
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
    if cell is None:
        new_cell += 1

    stmt = Cell.__table__.insert(
        on_duplicate='new_measures = new_measures + 1, '
                     'total_measures = total_measures + 1').values(
        created=measure.created, radio=measure.radio,
        mcc=measure.mcc, mnc=measure.mnc, lac=measure.lac, cid=measure.cid,
        new_measures=1, total_measures=1)
    session.execute(stmt)

    if userid is not None and new_cell > 0:
        # update user score
        process_score(userid, new_cell, session, key='new_cell')


def process_cell_measure(session, measure_data, entries, userid=None):
    cell_measures = []
    # TODO group by unique cell
    for entry in entries:
        cell_measure = create_cell_measure(measure_data, entry)
        # use more specific cell type or
        # fall back to less precise measure
        if entry.get('radio'):
            cell_measure.radio = RADIO_TYPE.get(entry['radio'], -1)
        else:
            cell_measure.radio = measure_data['radio']
        update_cell_measure_count(cell_measure, session, userid=userid)
        cell_measures.append(cell_measure)
    session.add_all(cell_measures)
    return cell_measures


@celery.task(base=DatabaseTask, bind=True)
def insert_cell_measure(self, measure_data, entries, userid=None):
    try:
        cell_measures = []
        with self.db_session() as session:
            cell_measures = process_cell_measure(
                session, measure_data, entries, userid=userid)
            session.commit()
        return len(cell_measures)
    except IntegrityError as exc:  # pragma: no cover
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


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


def update_wifi_measure_count(wifi_key, wifis, created, session, userid=None):
    new_wifi = 0
    if wifi_key not in wifis:
        new_wifi += 1
        wifis[wifi_key] = True

    stmt = Wifi.__table__.insert(
        on_duplicate='new_measures = new_measures + 1, '
                     'total_measures = total_measures + 1').values(
        key=wifi_key, created=created,
        new_measures=1, total_measures=1)
    session.execute(stmt)

    if userid is not None and new_wifi > 0:
        # update user score
        process_score(userid, new_wifi, session, key='new_wifi')


def create_wifi_measure(measure_data, created, entry):
    return WifiMeasure(
        measure_id=measure_data['id'],
        created=created,
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


def process_wifi_measure(session, measure_data, entries, userid=None):
    wifi_measures = []
    wifi_keys = set([e['key'] for e in entries])
    # did we get measures for blacklisted wifis?
    blacked = session.query(WifiBlacklist.key).filter(
        WifiBlacklist.key.in_(wifi_keys)).all()
    blacked = set([b[0] for b in blacked])
    # do we already know about these wifis?
    wifis = session.query(Wifi.key).filter(Wifi.key.in_(wifi_keys))
    wifis = dict([(w[0], True) for w in wifis.all()])
    created = decode_datetime(measure_data.get('created', ''))
    # TODO group by unique cell
    for entry in entries:
        wifi_key = entry['key']
        # convert frequency into channel numbers and remove frequency
        convert_frequency(entry)
        wifi_measures.append(create_wifi_measure(measure_data, created, entry))
        # update new/total measure counts
        if wifi_key not in blacked:
            # skip blacklisted wifi AP's
            update_wifi_measure_count(
                wifi_key, wifis, created, session, userid=userid)
    session.add_all(wifi_measures)
    return wifi_measures


@celery.task(base=DatabaseTask, bind=True)
def insert_wifi_measure(self, measure_data, entries, userid=None):
    wifi_measures = []
    try:
        with self.db_session() as session:
            wifi_measures = process_wifi_measure(
                session, measure_data, entries, userid=userid)
            session.commit()
        return len(wifi_measures)
    except IntegrityError as exc:
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
