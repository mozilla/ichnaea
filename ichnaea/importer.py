import argparse
import csv
import sys

from pyramid.paster import bootstrap
from sqlalchemy import func

from ichnaea.db import CellDB, Cell


def _int(value):
    try:
        return int(value)
    except ValueError:
        return 0


def load_file(settings, source_file, batch_size=10000):
    db = CellDB(settings['celldb'])
    session = db.session()
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
                cell = dict(
                    id=id_,
                    # TODO figure out if we have cdma networks
                    radio=0,
                    lat=int(float(fields[2]) * 1000000),
                    lon=int(float(fields[3]) * 1000000),
                    mcc=_int(fields[4]),
                    mnc=_int(fields[5]),
                    lac=_int(fields[6]),
                    cid=_int(fields[7]),
                    range=_int(fields[8]),
                )
            except (ValueError, IndexError):
                continue
            cells.append(cell)

            # commit every 1000 new records
            counter += 1
            if counter % batch_size == 0:
                session.execute(cell_insert, cells)
                print('Added %s records.' % counter)
                cells = []

        # commit the rest
        session.execute(cell_insert, cells)
        print('Added %s records.' % counter)
        session.commit()
        session.execute('VACUUM')
    # return for tests
    return counter


def main(argv):
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Ichaneae Importer')

    parser.add_argument('config', help="config file")
    parser.add_argument('source', help="source file")
    args = parser.parse_args(argv[1:])

    env = bootstrap(args.config)
    settings = env['registry'].settings
    closer = env['closer']
    try:
        counter = load_file(settings, args.source)
    finally:
        closer()
    return counter


def console_entry():  # pragma: no cover
    main(sys.argv)
