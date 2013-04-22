import argparse
import csv

from pyramid.paster import bootstrap
from sqlalchemy import func

from ichnaea.db import CellDB, Cell


def _int(value):
    try:
        return int(value)
    except ValueError:
        return 0


def load_file(settings, source_file):
    db = CellDB(settings['celldb'])
    session = db.session()
    result = session.query(func.max(Cell.id)).first()
    max_id = result[0]
    cell_insert = Cell.__table__.insert()

    with open(source_file, 'r') as fd:
        reader = csv.reader(fd, delimiter=',')
        cells = []
        counter = 0

        for fields in reader:
            id_ = int(fields[0])
            # skip already processed items - we rely on the data file
            # to be sorted by id
            if id_ <= max_id:
                continue

            try:
                cell = dict(
                    id=id_,
                    lat=int(float(fields[1]) * 1000000),
                    lon=int(float(fields[2]) * 1000000),
                    mcc=_int(fields[3]),
                    mnc=_int(fields[4]),
                    lac=_int(fields[5]),
                    cid=_int(fields[6]),
                    range=_int(fields[7]),
                )
            except ValueError:
                continue
            cells.append(cell)

            # commit every 1000 new records
            counter += 1
            if counter % 10000 == 0:
                session.execute(cell_insert, cells)
                print('Added %s records.' % counter)
                cells = []

        # commit the rest
        session.execute(cell_insert, cells)
        print('Added %s records.' % counter)
        session.commit()
        session.execute('VACUUM')
    # return db for tests
    return db


def main():
    parser = argparse.ArgumentParser(description='Ichaneae Importer')

    parser.add_argument('config', help="config file")
    parser.add_argument('source', help="source file")
    args = parser.parse_args()

    env = bootstrap(args.config)
    settings = env['registry'].settings
    closer = env['closer']
    try:
        load_file(settings, args.source)
    finally:
        closer()


if __name__ == '__main__':
    main()
