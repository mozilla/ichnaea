import argparse
import csv
import sys

from konfig import Config
from sqlalchemy import func

from ichnaea.db import Database, Cell
from ichnaea.decimaljson import to_precise_int


def _int(value):
    try:
        return int(value)
    except ValueError:
        return 0


def load_file(session, source_file, batch_size=10000):
    result = session.query(func.max(Cell.id)).first()
    max_id = result[0]
    cell_insert = Cell.__table__.insert()

    with open(source_file, 'r') as fd:
        reader = csv.reader(fd, delimiter=';')
        cells = []
        counter = 0

        for fields in reader:
            id_ = int(fields[0])
            # skip already processed items - we rely on the data file
            # to have consistent ids between exports
            if id_ <= max_id:  # pragma: no cover
                continue
            try:
                radio = 0
                mcc = _int(fields[4])
                if mcc > 1000:  # pragma: no cover
                    continue
                mnc = _int(fields[5])
                if radio == 0 and mnc > 1000:  # pragma: no cover
                    continue
                elif radio == 1 and mnc > 32767:  # pragma: no cover
                    continue
                cell = dict(
                    id=id_,
                    # TODO figure out if we have cdma networks
                    radio=radio,
                    lat=to_precise_int(fields[2]),
                    lon=to_precise_int(fields[3]),
                    mcc=mcc,
                    mnc=mnc,
                    lac=_int(fields[6]),
                    cid=_int(fields[7]),
                    range=_int(fields[8]),
                )
            except (ValueError, IndexError):
                continue
            cells.append(cell)

            # flush every 1000 new records
            counter += 1
            if counter % batch_size == 0:
                session.execute(cell_insert, cells)
                session.flush()
                print('Added %s records.' % counter)
                cells = []

    # add the rest
    session.execute(cell_insert, cells)
    return counter


def main(argv):
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Location Importer')

    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('config', help="config file")
    parser.add_argument('source', help="source file")
    args = parser.parse_args(argv[1:])
    settings = Config(args.config).get_map('ichnaea')
    db = Database(
        settings['db_master'],
        socket=settings.get('db_master_socket'),
        create=False,
    )
    session = db.session()
    added = load_file(session, args.source)
    print('Added %s records.' % added)
    if args.dry_run:
        session.rollback()
    else:  # pragma: no cover
        session.commit()
    return added


def console_entry():  # pragma: no cover
    main(sys.argv)
