from collections import (
    defaultdict,
    namedtuple,
)

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

CellKey = namedtuple('CellKey', 'radio mcc mnc lac cid')


def create_cell_measure(measure_data, entry):
    if 'lac' not in entry or entry['lac'] >= 2147483647:
        entry['lac'] = -1
    if 'cid' not in entry or entry['cid'] >= 2147483647:
        entry['cid'] = -1

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
        lac=entry['lac'],
        cid=entry['cid'],
        psc=entry.get('psc', 0),
        asu=entry.get('asu', 0),
        signal=entry.get('signal', 0),
        ta=entry.get('ta', 0),
    )


def update_cell_measure_count(cell_key, count, created, session):
    if (cell_key.radio == -1 or cell_key.lac == -1 or cell_key.cid == -1):
        # only update data for complete records
        return 0

    # do we already know about this cell?
    query = session.query(Cell).filter(
        Cell.radio == cell_key.radio).filter(
        Cell.mcc == cell_key.mcc).filter(
        Cell.mnc == cell_key.mnc).filter(
        Cell.lac == cell_key.lac).filter(
        Cell.cid == cell_key.cid
    )
    cell = query.first()
    new_cell = 0
    if cell is None:
        new_cell = 1

    stmt = Cell.__table__.insert(
        on_duplicate='new_measures = new_measures + %s, '
                     'total_measures = total_measures + %s' % (count, count)
    ).values(
        created=created, radio=cell_key.radio,
        mcc=cell_key.mcc, mnc=cell_key.mnc, lac=cell_key.lac, cid=cell_key.cid,
        new_measures=count, total_measures=count)
    session.execute(stmt)
    return new_cell


def process_cell_measure(session, measure_data, entries, userid=None):
    cell_count = defaultdict(int)
    cell_measures = []
    created = decode_datetime(measure_data.get('created', ''))

    # process entries
    for entry in entries:
        cell_measure = create_cell_measure(measure_data, entry)
        # use more specific cell type or
        # fall back to less precise measure
        if entry.get('radio'):
            cell_measure.radio = RADIO_TYPE.get(entry['radio'], -1)
        else:
            cell_measure.radio = measure_data['radio']
        cell_measures.append(cell_measure)
        # group per unique cell
        cell_count[CellKey(cell_measure.radio, cell_measure.mcc,
                           cell_measure.mnc, cell_measure.lac,
                           cell_measure.cid)] += 1

    # update new/total measure counts
    new_cells = 0
    for cell_key, count in cell_count.items():
        new_cells += update_cell_measure_count(
            cell_key, count, created, session)

    # update user score
    if userid is not None and new_cells > 0:
        process_score(userid, new_cells, session, key='new_cell')

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
    wifi_count = defaultdict(int)
    wifi_keys = set([e['key'] for e in entries])
    created = decode_datetime(measure_data.get('created', ''))

    # did we get measures for blacklisted wifis?
    blacked = session.query(WifiBlacklist.key).filter(
        WifiBlacklist.key.in_(wifi_keys)).all()
    blacked = set([b[0] for b in blacked])

    # process entries
    for entry in entries:
        wifi_key = entry['key']
        # convert frequency into channel numbers and remove frequency
        convert_frequency(entry)
        wifi_measures.append(create_wifi_measure(measure_data, created, entry))
        if wifi_key not in blacked:
            # skip blacklisted wifi AP's
            wifi_count[wifi_key] += 1

    # update user score
    if userid is not None:
        # do we already know about any wifis?
        white_keys = wifi_keys - blacked
        if white_keys:
            wifis = session.query(Wifi.key).filter(Wifi.key.in_(white_keys))
            wifis = dict([(w[0], True) for w in wifis.all()])
        else:
            wifis = {}
        # subtract known wifis from all unique wifis
        new_wifis = len(wifi_count) - len(wifis)
        if new_wifis > 0:
            process_score(userid, new_wifis, session, key='new_wifi')

    # update new/total measure counts
    for wifi_key, num in wifi_count.items():
        stmt = Wifi.__table__.insert(
            on_duplicate='new_measures = new_measures + %s, '
                         'total_measures = total_measures + %s' % (num, num)
        ).values(
            key=wifi_key, created=created,
            new_measures=num, total_measures=num)
        session.execute(stmt)

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
