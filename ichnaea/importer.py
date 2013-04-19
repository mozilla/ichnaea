import argparse

from pyramid.paster import bootstrap
from sqlalchemy import func

from ichnaea.db import Database, Cell


def _int(value):
    try:
        return int(value)
    except ValueError:
        return 0


def load_file(settings, source_file):
    db = Database(settings['database'])
    session = db.session()
    result = session.query(func.max(Cell.id)).first()
    max_id = result[0]

    with open(source_file, 'r') as fd:
        cells = []
        counter = 0

        for line in fd.readlines():
            fields = line.split(',')
            id_ = int(fields[0])
            # skip already processed items - we rely on the data file
            # to be sorted by id
            if id_ <= max_id:
                continue

            try:
                cell = Cell(
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
                print('Adding 10000 new records.')
                session.add_all(cells)
                session.commit()
                cells = []

        # commit the rest
        session.add_all(cells)
        session.commit()


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
