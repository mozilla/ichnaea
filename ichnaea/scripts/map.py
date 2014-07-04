import argparse
from contextlib import contextmanager
import hashlib
import os
from random import Random
import shutil
import sys
import tempfile

import boto
from sqlalchemy import text

from ichnaea.config import read_config
from ichnaea.db import Database
from ichnaea.heka_logging import configure_heka


@contextmanager
def tempdir():
    workdir = tempfile.mkdtemp()
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir)


def export_to_csv(db, filename):
    session = db.session()
    # Order by id to keep a stable ordering.
    stmt = text('select lat, lon from mapstat '
                'order by id limit :l offset :o')

    # Set up a pseudo random generator with a fixed seed to prevent
    # datamap tiles from changing with every generation.
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


def upload_to_s3(bucketname, tiles):
    tiles = os.path.abspath(tiles)

    conn = boto.connect_s3()
    bucket = conn.get_bucket(bucketname, validate=False)
    result = {'changed': 0, 'unchanged': 0, 'new': 0}

    def _key(name):
        try:
            return int(name)
        except Exception:
            return -1

    for name in sorted(os.listdir(tiles), key=_key):
        folder = os.path.join(tiles, name)
        if not os.path.isdir(folder):
            continue

        for root, dirs, files in os.walk(folder):
            rel_root = 'tiles/' + root.lstrip(tiles) + '/'
            for f in files:
                if not f.endswith('.png'):
                    continue
                filename = root + os.sep + f
                keyname = rel_root + f
                key = bucket.get_key(keyname)
                changed = True
                if key is not None:
                    if os.path.getsize(filename) != key.size:
                        # do the file sizes match?
                        changed = True
                    else:
                        remote_md5 = key.etag.strip('"')
                        with open(filename, 'rb') as fd:
                            local_md5 = hashlib.md5(fd.read()).hexdigest()
                        if local_md5 == remote_md5:
                            # do the md5/etags match?
                            changed = False
                if changed:
                    if key is None:
                        result['new'] += 1
                        key = boto.s3.key.Key(bucketname)
                        key.key = keyname
                    else:
                        result['changed'] += 1
                    # TODO: activate once tested
                    # set correct metadata, acl, RR storage policy
                    # key.set_contents_from_filename(filename)
                else:
                    result['unchanged'] += 1

    return result


def generate(db, bucketname,
             upload=True, concurrency=2, datamaps='', output=None):
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

        if upload:
            result = upload_to_s3(bucketname, tiles)
            sys.stdout.write('Upload to S3: %s' % result)


def main(argv, _db_master=None, _heka_client=None):
    # run for example via:
    # bin/location_map --create --datamaps=/path/to/datamaps/ \
    #   --output=ichnaea/content/static/tiles/

    parser = argparse.ArgumentParser(
        prog=argv[0], description='Generate and upload datamap tiles.')

    parser.add_argument('--create', action='store_true',
                        help='Create tiles.')
    parser.add_argument('--upload', action='store_true',
                        help='Upload tiles to S3.')
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
        bucketname = conf.get('ichnaea', 's3_assets_bucket').strip('/')
        configure_heka(conf.filename, _heka_client=_heka_client)

        upload = False
        if args.upload:
            upload = bool(args.upload)

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
                 upload=upload,
                 concurrency=concurrency,
                 datamaps=datamaps,
                 output=output)
    else:
        parser.print_help()


def console_entry():  # pragma: no cover
    main(sys.argv)
