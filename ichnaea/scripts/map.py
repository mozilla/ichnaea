import argparse
from contextlib import contextmanager
import hashlib
import os
from random import Random
import shutil
import sys
import tempfile

import boto
from simplejson import dumps
from sqlalchemy import text

from ichnaea.config import read_config
from ichnaea.db import (
    Database,
    db_worker_session,
)
from ichnaea.log import (
    configure_raven,
    configure_stats,
)
from ichnaea import util

IMAGE_HEADERS = {
    'Content-Type': 'image/png',
    'Cache-Control': 'max-age=3600, public',
}
JSON_HEADERS = {
    'Content-Type': 'application/json',
    'Cache-Control': 'max-age=3600, public',
}


@contextmanager
def tempdir():
    workdir = tempfile.mkdtemp()
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir)


def system_call(cmd):  # pragma: no cover
    # testing hook
    return os.system(cmd)


def export_to_csv(session, filename, multiplier=5):
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

    result_rows = 0
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
            for row in rows:
                for i in xrange(multiplier):
                    # keep calling random even if we skip the lines
                    # to preserve the pseudo-random sequence
                    lat = (row[0] + random()) / 1000.0
                    lon = (row[1] + random()) / 1000.0
                    if row[0] != 0 or row[1] != 0:
                        append(pattern % (lat, lon))
            fd.writelines(lines)
            result_rows += len(lines)
            offset += batch

    return result_rows


def upload_to_s3(bucketname, tiles):  # pragma: no cover
    tiles = os.path.abspath(tiles)

    conn = boto.connect_s3()
    bucket = conn.get_bucket(bucketname, validate=False)
    result = {
        'tile_changed': 0,
        'tile_deleted': 0,
        'tile_unchanged': 0,
        'tile_new': 0,
        's3_put': 0,
        's3_list': 0,
    }

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
            rel_root_len = len(rel_root)
            filtered_files = [f for f in files if f.endswith('.png')]
            if not filtered_files:
                continue
            # get all the keys
            keys = {}
            result['s3_list'] += 1
            for key in bucket.list(prefix=rel_root):
                rel_name = key.name[rel_root_len:]
                keys[rel_name] = key
            for f in filtered_files:
                filename = root + os.sep + f
                keyname = rel_root + f
                key = keys.pop(f, None)
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
                        result['tile_new'] += 1
                        key = boto.s3.key.Key(bucket)
                        key.key = keyname
                    else:
                        result['tile_changed'] += 1
                    # upload or update the key
                    result['s3_put'] += 1
                    key.set_contents_from_filename(
                        filename,
                        headers=IMAGE_HEADERS,
                        reduced_redundancy=True)
                else:
                    result['tile_unchanged'] += 1
            # delete orphaned files
            for rel_name, key in keys.items():
                result['tile_deleted'] += 1
                key.delete()

    # Update status file
    data = {'updated': util.utcnow().isoformat()}
    k = boto.s3.key.Key(bucket)
    k.key = 'tiles/data.json'
    k.set_contents_from_string(
        dumps(data),
        headers=JSON_HEADERS,
        reduced_redundancy=True)

    return result


def generate(db, bucketname, raven_client, stats_client,
             upload=True, concurrency=2, datamaps='', output=None):
    datamaps_encode = os.path.join(datamaps, 'encode')
    datamaps_enumerate = os.path.join(datamaps, 'enumerate')
    datamaps_render = os.path.join(datamaps, 'render')

    with tempdir() as workdir:
        csv = os.path.join(workdir, 'map.csv')

        with stats_client.timer("datamaps.export_to_csv"):
            with db_worker_session(db) as session:
                result_rows = export_to_csv(session, csv)

        stats_client.timing('datamaps.csv_rows', result_rows)

        # create shapefile / quadtree
        shapes = os.path.join(workdir, 'shapes')
        cmd = '{encode} -z15 -o {output} {input}'.format(
            encode=datamaps_encode,
            output=shapes,
            input=csv)

        with stats_client.timer("datamaps.encode"):
            system_call(cmd)

        # render tiles
        if output:
            tiles = output
        else:
            tiles = os.path.join(workdir, 'tiles')
        cmd = ("{enumerate} -z{zoom} {shapes} | xargs -L1 -P{concurrency} "
               "sh -c 'mkdir -p {output}/$2/$3; {render} "
               "-B 12:0.0379:0.874 -c0088FF -t0 "
               "-O 16:1600:1.5 -G 0.5{extra} $1 $2 $3 $4 | "
               "pngquant --speed=3 --quality=65-95 32 > "
               "{output}/$2/$3/$4{suffix}.png' dummy")

        zoom_0_cmd = cmd.format(
            enumerate=datamaps_enumerate,
            zoom=0,
            shapes=shapes,
            concurrency=concurrency,
            render=datamaps_render,
            output=tiles,
            extra=' -T 512',
            suffix='@2x')

        # create high-res version for zoom level 0
        system_call(zoom_0_cmd)

        zoom_all_cmd = cmd.format(
            enumerate=datamaps_enumerate,
            zoom=13,
            shapes=shapes,
            concurrency=concurrency,
            render=datamaps_render,
            output=tiles,
            extra='',
            suffix='')

        with stats_client.timer("datamaps.render"):
            system_call(zoom_all_cmd)

        if upload:  # pragma: no cover
            with stats_client.timer("datamaps.upload_to_s3"):
                result = upload_to_s3(bucketname, tiles)

            for metric, value in result.items():
                stats_client.timing('datamaps.%s' % metric, value)


def main(argv, _db_rw=None,
         _raven_client=None, _stats_client=None):
    # run for example via:
    # bin/location_map --create --upload --datamaps=/path/to/datamaps/ \
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
        if _db_rw:
            db = _db_rw
        else:  # pragma: no cover
            db = Database(conf.get('ichnaea', 'db_master'))
        bucketname = conf.get('ichnaea', 's3_assets_bucket').strip('/')
        raven_client = configure_raven(
            conf.get('ichnaea', 'sentry_dsn'), _client=_raven_client)
        stats_client = configure_stats(
            conf.get('ichnaea', 'statsd_host'), _client=_stats_client)

        upload = False
        if args.upload:  # pragma: no cover
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

        try:
            with stats_client.timer("datamaps.total_time"):
                generate(db, bucketname, raven_client, stats_client,
                         upload=upload,
                         concurrency=concurrency,
                         datamaps=datamaps,
                         output=output)
        except Exception:  # pragma: no cover
            raven_client.captureException()
            raise
    else:  # pragma: no cover
        parser.print_help()


def console_entry():  # pragma: no cover
    main(sys.argv)
