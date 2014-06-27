import argparse
from contextlib import contextmanager
import os
from random import Random
import shutil
import sys
import tempfile

from sqlalchemy import text

from ichnaea.config import read_config
from ichnaea.db import Database


@contextmanager
def tempdir():
    workdir = tempfile.mkdtemp()
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir)


def export_to_csv(db, filename):
    session = db.session()
    # restrict lat/lon to web mercator projection values
    stmt = text('select lat, lon from mapstat where `key` = 2 and '
                'lat < 85051 and lat > -85051 and lon < 180000 and '
                'lon > -180000 order by lat, lon limit :l offset :o')

    # Set up a pseudo random generator with a fixed seed to prevent
    # datamap tiles from changing with every generation
    pseudorandom = Random()
    pseudorandom.seed(42)
    random = pseudorandom.random
    offset = 0
    batch = 200000
    pattern = '%.6f,%.6f\n'

    # export mapstat mysql table as csv to local file
    with open(filename, 'w') as fd:
        while True:
            result = session.execute(stmt.bindparams(o=offset, l=batch))
            rows = result.fetchall()
            result.close()
            if not rows:
                break
            lines = []
            append = lines.append
            for r in rows:
                for i in xrange(5):
                    lat = (r[0] + random()) / 1000.0
                    lon = (r[1] + random()) / 1000.0
                    append(pattern % (lat, lon))
            fd.writelines(lines)
            offset += batch


def generate(db, bucketname, concurrency=2, datamaps='', output=None):
    datamaps_encode = os.path.join(datamaps, 'encode')
    datamaps_enumerate = os.path.join(datamaps, 'enumerate')
    datamaps_render = os.path.join(datamaps, 'render')

    with tempdir() as workdir:
        csv = os.path.join(workdir, 'map.csv')
        export_to_csv(db, csv)

        # create shapefile / quadtree
        shapes = os.path.join(workdir, 'shapes')
        cmd = '{encode} -z15 -o {output} {input}'.format(
            encode=datamaps_encode,
            output=shapes,
            input=csv)
        os.system(cmd)

        # render tiles
        if output:
            tiles = output
        else:
            tiles = os.path.join(workdir, 'tiles')
        cmd = ('{enumerate} -z13 {shapes} | xargs -L1 -P{concurrency} '
               '{render} -o {output} -B 12:0.0379:0.874 -c0088FF -t0 '
               '-O 16:1600:1.5 -G 0.5')
        cmd = cmd.format(
            enumerate=datamaps_enumerate,
            shapes=shapes,
            concurrency=concurrency,
            render=datamaps_render,
            output=tiles)
        os.system(cmd)


def main(argv, _db_master=None):
    # run for example via:
    # bin/location_map --create --datamaps=/path/to/datamaps/ \
    #   --output=ichnaea/content/static/tiles/

    parser = argparse.ArgumentParser(
        prog=argv[0], description='Generate and upload datamap tiles.')

    parser.add_argument('--create', action='store_true',
                        help='Create tiles.')
    parser.add_argument('--concurrency', default=2,
                        help='How many concurrent render processes to use?')
    parser.add_argument('--datamaps',
                        help='Directory of the datamaps tools.')
    parser.add_argument('--output',
                        help='Optional directory for local tile output.')

    args = parser.parse_args(argv[1:])

    if args.create:
        conf = read_config()
        db = Database(conf.get('ichnaea', 'db_master'))
        bucketname = conf.get('ichnaea', 's3_assets_bucket')

        concurrency = 2
        if args.concurrency:
            concurrency = int(args.concurrency)

        datamaps = ''
        if args.datamaps:
            datamaps = os.path.abspath(args.datamaps)

        output = None
        if args.output:
            output = os.path.abspath(args.output)

        generate(db, bucketname,
                 concurrency=concurrency, datamaps=datamaps, output=output)
    else:
        parser.print_help()


def console_entry():  # pragma: no cover
    main(sys.argv)
