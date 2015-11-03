import argparse
import hashlib
import os
import os.path
import shutil
import sys

import billiard
import boto
from simplejson import dumps
from sqlalchemy import text

from ichnaea.config import read_config
from ichnaea.db import (
    configure_db,
    db_worker_session,
)
from ichnaea.geocalc import random_points
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

if sys.platform == 'darwin':  # pragma: no cover
    ZCAT = 'gzcat'
else:  # pragma: no cover
    ZCAT = 'zcat'


def export_file(db_url, filename, min_lat, max_lat, min_lon, max_lon,
                _db_rw=None, _session=None):
    # this is executed in a worker process
    stmt = text('''\
SELECT
lat, lon,
CAST(ROUND(DATEDIFF(CURDATE(), `time`) / 30) AS UNSIGNED) as `num`
FROM mapstat
WHERE
lat >= :min_lat AND lat < :max_lat AND
lon >= :min_lon AND lon < :max_lon
LIMIT :limit OFFSET :offset
'''.replace('\n', ' '))
    db = configure_db(db_url, _db=_db_rw)

    offset = 0
    limit = 100000

    result_rows = 0
    with util.gzip_open(filename, 'w', compresslevel=2) as fd:
        with db_worker_session(db, commit=False) as session:
            if _session is not None:
                # testing hook
                session = _session
            while True:
                result = session.execute(stmt.bindparams(
                    min_lat=min_lat, max_lat=max_lat,
                    min_lon=min_lon, max_lon=max_lon,
                    limit=limit, offset=offset))
                rows = result.fetchall()
                result.close()
                if not rows:
                    break

                lines = []
                extend = lines.extend
                for row in rows:
                    extend(random_points(row[0], row[1], row[2]))

                fd.writelines(lines)

                result_rows += len(lines)
                offset += limit

    if not result_rows:  # pragma: no cover
        os.remove(filename)

    db.engine.pool.dispose()
    return result_rows


def export_files(pool, db_url, csvdir):  # pragma: no cover
    jobs = []
    result_rows = 0
    # split the earth into 32 chunks
    lat_batch = 42526
    lon_batch = 45001
    # limited to Web Mercator bounds
    for lat in range(-85051, 85052, lat_batch):
        for lon in range(-180000, 180001, lon_batch):
            filename = os.path.join(csvdir, 'map_%s_%s.csv.gz' % (lat, lon))
            jobs.append(pool.apply_async(export_file,
                                         (db_url, filename,
                                          lat, lat + lat_batch,
                                          lon, lon + lon_batch)))

    for job in jobs:
        result_rows += job.get()

    return result_rows


def encode_file(name, csvdir, quaddir, datamaps_encode):  # pragma: no cover
    # this is executed in a worker process
    in_ = os.path.join(csvdir, name)
    out = os.path.join(quaddir, name.split('.')[0])

    cmd = '{zcat} {input} | {encode} -z15 -o {output}'.format(
        zcat=ZCAT,
        input=in_,
        encode=datamaps_encode,
        output=out)

    os.system(cmd)


def encode_files(pool, csvdir, quaddir, datamaps_encode):  # pragma: no cover
    jobs = []
    for name in os.listdir(csvdir):
        if name.startswith('map_') and name.endswith('.csv.gz'):
            jobs.append(pool.apply_async(
                encode_file,
                (name, csvdir, quaddir, datamaps_encode)))

    for job in jobs:
        job.get()

    return len(jobs)


def upload_to_s3(pool, bucketname, tiles):  # pragma: no cover
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


def generate(db_url, bucketname, raven_client, stats_client,
             upload=True, concurrency=2,
             datamaps='', output=None):  # pragma: no cover
    datamaps_encode = os.path.join(datamaps, 'encode')
    datamaps_enumerate = os.path.join(datamaps, 'enumerate')
    datamaps_merge = os.path.join(datamaps, 'merge')
    datamaps_render = os.path.join(datamaps, 'render')

    with util.selfdestruct_tempdir() as workdir:
        pool = billiard.Pool(processes=concurrency)

        if output:
            basedir = output
        else:
            basedir = workdir

        if not os.path.isdir(basedir):
            os.makedirs(basedir)

        # export datamap table to csv
        csvdir = os.path.join(basedir, 'csv')
        if not os.path.isdir(csvdir):
            os.mkdir(csvdir)

        with stats_client.timed('datamaps', tags=['func:export']):
            result_rows = export_files(pool, db_url, csvdir)

        stats_client.timing('datamaps', result_rows, tags=['count:csv_rows'])

        # create quadtrees
        quaddir = os.path.join(basedir, 'quadtrees')
        if os.path.isdir(quaddir):
            shutil.rmtree(quaddir)
        os.mkdir(quaddir)

        with stats_client.timed('datamaps', tags=['func:encode']):
            quadtrees = encode_files(pool, csvdir, quaddir, datamaps_encode)

        stats_client.timing('datamaps', quadtrees, tags=['count:quadtrees'])

        sys.stdout.flush()
        pool.close()
        pool.join()

        # merge quadtrees and make points unique
        shapes = os.path.join(basedir, 'shapes')
        if os.path.isdir(shapes):
            shutil.rmtree(shapes)

        in_ = os.path.join(quaddir, '*')
        cmd = '{merge} -u -o {output} {input}'.format(
            merge=datamaps_merge,
            input=in_,
            output=shapes)

        with stats_client.timed('datamaps', tags=['func:merge']):
            os.system(cmd)

        # render tiles
        tiles = os.path.join(basedir, 'tiles')
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
        os.system(zoom_0_cmd)

        zoom_all_cmd = cmd.format(
            enumerate=datamaps_enumerate,
            zoom=13,
            shapes=shapes,
            concurrency=concurrency,
            render=datamaps_render,
            output=tiles,
            extra='',
            suffix='')

        with stats_client.timed('datamaps', tags=['func:render']):
            os.system(zoom_all_cmd)

        if upload:  # pragma: no cover
            pool = billiard.Pool(processes=concurrency)

            with stats_client.timed('datamaps', tags=['func:upload']):
                result = upload_to_s3(pool, bucketname, tiles)

            pool.close()
            pool.join()

            for metric, value in result.items():
                stats_client.timing('datamaps', value,
                                    tags=['count:%s' % metric])


def main(argv, _raven_client=None, _stats_client=None):
    # run for example via:
    # bin/location_map --create --upload --datamaps=/path/to/datamaps/ \
    #   --output=ichnaea/content/static/tiles/

    parser = argparse.ArgumentParser(
        prog=argv[0], description='Generate and upload datamap tiles.')

    parser.add_argument('--create', action='store_true',
                        help='Create tiles?')
    parser.add_argument('--upload', action='store_true',
                        help='Upload tiles to S3?')
    parser.add_argument('--concurrency', default=2,
                        help='How many concurrent processes to use?')
    parser.add_argument('--datamaps',
                        help='Directory of the datamaps tools.')
    parser.add_argument('--output',
                        help='Optional directory for output files.')

    args = parser.parse_args(argv[1:])
    if args.create:
        conf = read_config()
        db_url = conf.get('database', 'rw_url')

        raven_client = configure_raven(
            conf.get('sentry', 'dsn'),
            transport='sync', _client=_raven_client)

        stats_client = configure_stats(conf, _client=_stats_client)

        bucketname = conf.get('assets', 'bucket').strip('/')

        upload = False
        if args.upload:
            upload = bool(args.upload)

        concurrency = billiard.cpu_count()
        if args.concurrency:
            concurrency = int(args.concurrency)

        datamaps = ''
        if args.datamaps:
            datamaps = os.path.abspath(args.datamaps)

        output = None
        if args.output:
            output = os.path.abspath(args.output)

        try:
            with stats_client.timed('datamaps', tags=['func:main']):
                generate(db_url, bucketname, raven_client, stats_client,
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
