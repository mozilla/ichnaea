"""
Generate datamap image tiles and upload them to Amazon S3.

Script is installed as `location_map`.
"""

import argparse
import hashlib
from json import dumps
import os
import os.path
import shutil
import sys

import billiard
import boto3
import markus
from sqlalchemy import text

from ichnaea.conf import settings
from ichnaea.models.content import DataMap, decode_datamap_grid
from ichnaea.db import configure_db, db_worker_session
from geocalc import random_points
from ichnaea.log import configure_raven, configure_stats
from ichnaea import util

try:
    from os import scandir
except ImportError:
    from scandir import scandir

if sys.platform == "darwin":
    ZCAT = "gzcat"
else:
    ZCAT = "zcat"


METRICS = markus.get_metrics()


def recursive_scandir(top):
    for entry in scandir(top):
        yield entry
        if entry.is_dir():
            for subentry in recursive_scandir(entry.path):
                yield subentry


def export_file(filename, tablename, _db=None, _session=None):
    # this is executed in a worker process
    stmt = text(
        """\
SELECT
`grid`, CAST(ROUND(DATEDIFF(CURDATE(), `modified`) / 30) AS UNSIGNED) as `num`
FROM {tablename}
WHERE `grid` > :grid
ORDER BY `grid`
LIMIT :limit
""".format(
            tablename=tablename
        ).replace(
            "\n", " "
        )
    )

    db = configure_db("ro", _db=_db, pool=False)
    min_grid = b""
    limit = 200000

    result_rows = 0
    with util.gzip_open(filename, "w", compresslevel=2) as fd:
        with db_worker_session(db, commit=False) as session:
            if _session is not None:
                # testing hook
                session = _session
            while True:
                result = session.execute(stmt.bindparams(limit=limit, grid=min_grid))
                rows = result.fetchall()
                result.close()
                if not rows:
                    break

                lines = []
                extend = lines.extend
                for row in rows:
                    lat, lon = decode_datamap_grid(row.grid)
                    extend(random_points(lat, lon, row.num))

                fd.writelines(lines)
                result_rows += len(lines)
                min_grid = rows[-1].grid

    if not result_rows:
        os.remove(filename)

    db.close()
    return result_rows


def export_files(pool, csvdir):
    jobs = []
    result_rows = 0
    for shard_id, shard in sorted(DataMap.shards().items()):
        # sorting the shards prefers the north which contains more
        # data points than the south
        filename = os.path.join(csvdir, "map_%s.csv.gz" % shard_id)
        jobs.append(pool.apply_async(export_file, (filename, shard.__tablename__)))

    for job in jobs:
        result_rows += job.get()

    return result_rows


def encode_file(name, csvdir, quaddir):
    # this is executed in a worker process
    cmd = "{zcat} {input} | encode -z13 -o {output}".format(
        zcat=ZCAT,
        input=os.path.join(csvdir, name),
        output=os.path.join(quaddir, name.split(".")[0]),
    )

    os.system(cmd)


def encode_files(pool, csvdir, quaddir):
    jobs = []
    for name in os.listdir(csvdir):
        if name.startswith("map_") and name.endswith(".csv.gz"):
            jobs.append(pool.apply_async(encode_file, (name, csvdir, quaddir)))

    for job in jobs:
        job.get()

    return len(jobs)


def merge_files(quaddir, shapes):
    cmd = "merge -u -o {output} {input}".format(
        input=os.path.join(quaddir, "map*"), output=shapes
    )

    os.system(cmd)


def render_tiles(shapes, tiles, concurrency, max_zoom):
    cmd = (
        "enumerate -z{zoom} {shapes} | xargs -L1 -P{concurrency} "
        "sh -c 'mkdir -p {output}/$2/$3; render "
        "-B 12:0.0379:0.874 -c0088FF -t0 "
        "-O 16:1600:1.5 -G 0.5{extra} $1 $2 $3 $4 | "
        "pngquant --speed=3 --quality=65-95 32 > "
        "{output}/$2/$3/$4{suffix}.png' dummy"
    )

    zoom_0_cmd = cmd.format(
        zoom=0,
        shapes=shapes,
        concurrency=concurrency,
        output=tiles,
        extra=" -T 512",
        suffix="@2x",
    )

    zoom_all_cmd = cmd.format(
        zoom=max_zoom,
        shapes=shapes,
        concurrency=concurrency,
        output=tiles,
        extra="",
        suffix="",
    )

    # Create high-res version for zoom level 0.
    os.system(zoom_0_cmd)
    os.system(zoom_all_cmd)


def upload_folder(bucketname, bucket_prefix, tiles, folder):
    # this is executed in a worker process
    result = {"tile_changed": 0, "tile_deleted": 0, "tile_new": 0, "tile_unchanged": 0}

    # Get all the S3 objects.
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(bucketname)

    key_root = bucket_prefix + folder[len(tiles) :].lstrip("/") + "/"
    objs = {}
    for obj in bucket.objects.filter(Prefix=key_root):
        objs[obj.key[len(bucket_prefix) :]] = obj

    # Traverse local file system
    for entry in recursive_scandir(folder):
        if not entry.is_file() or not entry.name.endswith(".png"):
            continue

        obj_name = entry.path[len(tiles) :].lstrip("/")
        obj = objs.pop(obj_name, None)
        changed = True

        if obj is not None:
            if entry.stat().st_size != obj.size:
                # Mismatched file sizes?
                changed = True
            else:
                remote_md5 = obj.etag.strip('"')
                with open(entry.path, "rb") as fd:
                    local_md5 = hashlib.md5(fd.read()).hexdigest()
                if local_md5 == remote_md5:
                    # Do the md5/etags match?
                    changed = False

        if changed:
            if obj is None:
                obj = bucket.Object(bucket_prefix + obj_name)
                result["tile_new"] += 1
            else:
                result["tile_changed"] += 1

            # Create or update the object.
            obj.upload_file(
                entry.path,
                ExtraArgs={
                    "CacheControl": "max-age=3600, public",
                    "ContentType": "image/png",
                },
            )
        else:
            result["tile_unchanged"] += 1

    # Delete orphaned objects.
    if objs:
        result["tile_deleted"] += len(objs)
        key_values = list(objs.values())
        for i in range(0, len(key_values), 100):
            batch_keys = key_values[i : i + 100]
            bucket.delete_keys(batch_keys)

    return result


def upload_files(
    pool, bucketname, tiles, max_zoom, raven_client, bucket_prefix="tiles/"
):
    result = {"tile_changed": 0, "tile_deleted": 0, "tile_new": 0, "tile_unchanged": 0}

    zoom_levels = frozenset([str(i) for i in range(max_zoom + 1)])
    tiny_levels = frozenset([str(i) for i in range(min(10, max_zoom))])

    paths = []
    for entry in scandir(tiles):
        if not entry.is_dir() or entry.name not in zoom_levels:
            continue
        if entry.name in tiny_levels:
            # Process upper zoom levels in one go, as these contain
            # very few files. This avoids the overhead of repeated
            # Amazon S3 list calls and job scheduling.
            paths.append(entry.path)
        else:
            for subentry in scandir(entry.path):
                if subentry.is_dir():
                    paths.append(subentry.path)

    jobs = []
    for folder in paths:
        jobs.append(
            pool.apply_async(upload_folder, (bucketname, bucket_prefix, tiles, folder))
        )

    for job in jobs:
        try:
            folder_result = job.get()
            for key, value in folder_result.items():
                result[key] += value
        except Exception:
            raven_client.captureException()

    # Update status file
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(bucketname)

    obj = bucket.Object(bucket_prefix + "data.json")
    obj.put(
        Body=dumps({"updated": util.utcnow().isoformat()}),
        CacheControl="max-age=3600, public",
        ContentType="application/json",
    )

    return result


def generate(
    bucketname, raven_client, upload=True, concurrency=2, max_zoom=11, output=None
):
    with util.selfdestruct_tempdir() as workdir:
        pool = billiard.Pool(processes=concurrency)

        if output:
            basedir = output
        else:
            basedir = workdir

        if not os.path.isdir(basedir):
            os.makedirs(basedir)

        # Concurrently export datamap table to CSV files.
        csvdir = os.path.join(basedir, "csv")
        if not os.path.isdir(csvdir):
            os.mkdir(csvdir)

        with METRICS.timer("datamaps", tags=["func:export"]):
            result_rows = export_files(pool, csvdir)

        METRICS.timing("datamaps", result_rows, tags=["count:csv_rows"])

        # Concurrently create quadtrees out of CSV files.
        quaddir = os.path.join(basedir, "quadtrees")
        if os.path.isdir(quaddir):
            shutil.rmtree(quaddir)
        os.mkdir(quaddir)

        with METRICS.timer("datamaps", tags=["func:encode"]):
            quadtrees = encode_files(pool, csvdir, quaddir)

        METRICS.timing("datamaps", quadtrees, tags=["count:quadtrees"])

        pool.close()
        pool.join()

        # Merge quadtrees and make points unique. This process cannot
        # be made concurrent.
        shapes = os.path.join(basedir, "shapes")
        if os.path.isdir(shapes):
            shutil.rmtree(shapes)

        with METRICS.timer("datamaps", tags=["func:merge"]):
            merge_files(quaddir, shapes)

        # Render tiles, using xargs -P to get concurrency.
        tiles = os.path.abspath(os.path.join(basedir, "tiles"))

        with METRICS.timer("datamaps", tags=["func:render"]):
            render_tiles(shapes, tiles, concurrency, max_zoom)

        if upload:
            # The upload process is largely network I/O bound, so we
            # can use more processes compared to the CPU bound tasks.
            pool = billiard.Pool(processes=concurrency * 2)

            with METRICS.timer("datamaps", tags=["func:upload"]):
                result = upload_files(pool, bucketname, tiles, max_zoom, raven_client)

            pool.close()
            pool.join()

            for metric, value in result.items():
                METRICS.timing("datamaps", value, tags=["count:%s" % metric])


def main(argv, _raven_client=None, _bucketname=None):
    # run for example via:
    # bin/location_map --create --upload \
    #   --output=ichnaea/content/static/tiles/

    parser = argparse.ArgumentParser(
        prog=argv[0], description="Generate and upload datamap tiles."
    )

    parser.add_argument("--create", action="store_true", help="Create tiles?")
    parser.add_argument("--upload", action="store_true", help="Upload tiles to S3?")
    parser.add_argument(
        "--concurrency", default=2, help="How many concurrent processes to use?"
    )
    parser.add_argument("--output", help="Optional directory for output files.")

    args = parser.parse_args(argv[1:])
    if args.create:
        raven_client = configure_raven(transport="sync", _client=_raven_client)

        configure_stats()

        bucketname = _bucketname
        if not _bucketname:
            bucketname = settings("asset_bucket")
            if bucketname:
                bucketname = bucketname.strip("/")

        upload = False
        if args.upload:
            upload = bool(args.upload)

        concurrency = billiard.cpu_count()
        if args.concurrency:
            concurrency = int(args.concurrency)

        output = None
        if args.output:
            output = os.path.abspath(args.output)

        try:
            with METRICS.timer("datamaps", tags=["func:main"]):
                generate(
                    bucketname,
                    raven_client,
                    upload=upload,
                    concurrency=concurrency,
                    output=output,
                )
        except Exception:
            raven_client.captureException()
            raise
    else:
        parser.print_help()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
