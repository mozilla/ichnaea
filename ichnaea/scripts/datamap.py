#!/usr/bin/env python3
"""
Generate datamap image tiles and upload them to Amazon S3.

The process is:

1. Export data from datamap tables to CSV.
   The data is exported as pairs of latitude and longitude,
   converted into 0 to 6 pairs randomly around that point.
2. Convert the data into quadtree structures.
   This structure is more efficient for finding the points that
   apply to a tile.
3. Merge the per-table quadtrees into a single file
4. Generate tiles for each zoom level.
   More tiles, covering a smaller distance, are created at each
   higher zoom level.
5. Update the S3 bucket with the new tiles.
   The MD5 checksum is used to determine if a tile is unchanged.
   New tiles are uploaded, and orphaned tiles are deleted.

The quadtree and tile generators are from:
https://github.com/ericfischer/datamaps

The generated tiles are minimized with pngquant:
https://pngquant.org
"""

import argparse
import glob
import hashlib
import os
import os.path
import shutil
import subprocess
import sys
import uuid
from json import dumps
from multiprocessing import Pool
from timeit import default_timer

import boto3
import botocore
import structlog
from more_itertools import chunked
from sqlalchemy import text

from geocalc import random_points
from ichnaea import util
from ichnaea.conf import settings
from ichnaea.db import configure_db, db_worker_session
from ichnaea.log import configure_logging, configure_raven
from ichnaea.models.content import DataMap, decode_datamap_grid


LOG = structlog.get_logger("ichnaea.scripts.datamap")
S3_BUCKETS = None  # Will be re-initialized in each pool thread


class Timer:
    """Context-based timer."""

    def __enter__(self):
        self.start = default_timer()
        return self

    def __exit__(self, *args):
        self.end = default_timer()
        self.duration_s = round(self.end - self.start, 3)

    @property
    def elapsed(self):
        return default_timer() - self.start


def generate(
    output_dir,
    bucket_name,
    raven_client,
    create=True,
    upload=True,
    concurrency=2,
    max_zoom=11,
):
    """
    Process datamaps tables into tiles and optionally upload them.

    :param output_dir: The base directory for working files and tiles
    :param bucket_name: The name of the S3 bucket for upload
    :param raven_client: A raven client to log exceptions
    :param upload: True (default) if tiles should be uploaded to S3
    :param concurrency: The number of simultanous worker processes
    :param max_zoom: The maximum zoom level to generate
    :return: Details of the process
    :rtype: dict
    """
    result = {}

    # Setup directories
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    csv_dir = os.path.join(output_dir, "csv")
    quadtree_dir = os.path.join(output_dir, "quadtrees")
    shapes_dir = os.path.join(output_dir, "shapes")
    tiles_dir = os.path.abspath(os.path.join(output_dir, "tiles"))

    if create:
        # Export datamap table to CSV files
        if not os.path.isdir(csv_dir):
            os.mkdir(csv_dir)

        row_count = None
        with Pool(processes=concurrency) as pool, Timer() as export_timer:
            row_count = export_to_csvs(pool, csv_dir)
        result["export_duration_s"] = export_timer.duration_s
        result["row_count"] = row_count
        LOG.debug(
            f"Exported {row_count:,} rows in {export_timer.duration_s:0.1f} seconds"
        )

        # Convert CSV files to per-table quadtrees
        if os.path.isdir(quadtree_dir):
            shutil.rmtree(quadtree_dir)
        os.mkdir(quadtree_dir)

        with Pool(processes=concurrency) as pool, Timer() as quadtree_timer:
            quadtree_count = csv_to_quadtrees(pool, csv_dir, quadtree_dir)
        result["quadtree_duration_s"] = quadtree_timer.duration_s
        result["quadtree_count"] = quadtree_count
        LOG.debug(
            f"Created {quadtree_count} quadtrees in {quadtree_timer.duration_s:0.1f} seconds"
        )

        # Merge quadtrees and make points unique.
        if os.path.isdir(shapes_dir):
            shutil.rmtree(shapes_dir)

        with Timer() as merge_timer:
            merge_quadtrees(quadtree_dir, shapes_dir)
        result["merge_duration_s"] = merge_timer.duration_s
        LOG.debug(f"Merged quadtrees in {merge_timer.duration_s:0.1f} seconds")

        # Render tiles
        with Pool(processes=concurrency) as pool, Timer() as render_timer:
            tile_count = render_tiles(pool, shapes_dir, tiles_dir, max_zoom)
        result["tile_count"] = tile_count
        result["render_duration_s"] = render_timer.duration_s
        LOG.debug(
            f"Rendered {tile_count} tiles in {render_timer.duration_s:0.1f} seconds"
        )

    if upload:
        # Sync local tiles with S3 bucket
        # Double concurrency since I/O rather than CPU bound
        with Pool(processes=concurrency * 2) as pool, Timer() as sync_timer:
            sync_counts = sync_tiles(
                pool, bucket_name, tiles_dir, max_zoom, raven_client
            )

        result["sync_duration_s"] = sync_timer.duration_s
        result.update(sync_counts)
        LOG.debug(
            f"Synced tiles to S3 in {sync_timer.duration_s:0.1f} seconds: "
            f"{sync_counts['tile_new']:,} new, "
            f"{sync_counts['tile_changed']:,} changed, "
            f"{sync_counts['tile_deleted']:,} deleted, "
            f"{sync_counts['tile_unchanged']:,} unchanged"
        )

        upload_status_file(bucket_name, result)

    return result


def export_to_csvs(pool, csvdir):
    """Export from database tables to CSV."""
    jobs = []
    result_rows = 0
    for shard_id, shard in sorted(DataMap.shards().items()):
        # sorting the shards prefers the north which contains more
        # data points than the south
        filename = os.path.join(csvdir, "map_%s.csv" % shard_id)
        jobs.append(pool.apply_async(export_to_csv, (filename, shard.__tablename__)))

    for job in jobs:
        result_rows += job.get()

    return result_rows


def csv_to_quadtrees(pool, csvdir, quadtree_dir):
    """Convert CSV to quadtrees."""
    jobs = []
    for name in os.listdir(csvdir):
        if name.startswith("map_") and name.endswith(".csv"):
            jobs.append(pool.apply_async(csv_to_quadtree, (name, csvdir, quadtree_dir)))

    for job in jobs:
        job.get()

    return len(jobs)


def merge_quadtrees(quadtree_dir, shapes_dir):
    """Merge multiple quadtree files into one, removing duplicates."""
    quadtree_files = glob.glob(os.path.join(quadtree_dir, "map*"))
    cmd = [
        "merge",
        "-u",  # Remove duplicates
        "-o",  # Output to...
        shapes_dir,  # shapes directory
    ] + quadtree_files  # input files
    subprocess.run(cmd, check=True, capture_output=True)


def render_tiles(pool, shapes_dir, tiles_dir, max_zoom, progress_seconds=5.0):
    """Render the tiles at all zoom levels, and the front-page 2x tile."""

    # Render tiles at all zoom levels
    tile_count = render_tiles_for_zoom_levels(pool, shapes_dir, tiles_dir, max_zoom)

    # Render front-page tile
    tile_count += render_tiles_for_zoom_levels(
        pool,
        shapes_dir,
        tiles_dir,
        max_zoom=0,
        tile_type="high-resolution tile",
        extra_args=("-T", "512"),  # Tile size 512 instead of default of 256
        suffix="@2x",  # Suffix for high-res variant images
    )

    return tile_count


def export_to_csv(filename, tablename, _db=None, _session=None):
    """Export a datamap table to a CSV file."""
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
    with open(filename, "w") as fd:
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


def csv_to_quadtree(name, csv_dir, quadtree_dir):
    """
    Convert a CSV file into a quadtree.

    encode is from https://github.com/ericfischer/datamaps
    """
    input_path = os.path.join(csv_dir, name)
    with open(input_path, "rb") as csv_file:
        csv = csv_file.read()

    output_path = os.path.join(quadtree_dir, name.split(".")[0])
    cmd = ["encode", "-z13", "-o", output_path]  # Allow a single pixel at zoom level 13
    subprocess.run(cmd, input=csv, check=True, capture_output=True)


def render_tiles_for_zoom_levels(
    pool,
    shapes_dir,
    tiles_dir,
    max_zoom,
    tile_type="tile",
    progress_seconds=5.0,
    **render_keywords,
):
    """Render tiles concurrently across the zoom level."""

    # Get the tile enumeration parameters
    tile_params = enumerate_tiles(shapes_dir, max_zoom)

    total = len(tile_params)
    LOG.debug(f"Rendering {total:,} {tile_type}{'' if total == 1 else 's'}...")

    # Create the directory structure
    create_tile_subfolders(tile_params, tiles_dir)

    # Create jobs to concurrently generate the tiles
    jobs = []
    keywords = {
        "tiles_dir": tiles_dir,
    }
    keywords.update(render_keywords)
    for params in tile_params:
        jobs.append(pool.apply_async(generate_tile, params, keywords))

    # Wait until complete, report progress
    with Timer() as timer:
        last_elapsed = 0.0
        rendered = 0
        for job in jobs:
            job.get()
            rendered += 1
            percent = rendered / total
            if timer.elapsed > (last_elapsed + progress_seconds):
                LOG.debug(
                    f"  Rendered {rendered:,} {tile_type}{'' if total == 1 else 's'} ({percent:.1%})"
                )
                last_elapsed = timer.elapsed

    return len(jobs)


def enumerate_tiles(shapes_dir, zoom):
    """Enumerate the zoom and tile positions combinations in the shapes quadtree."""
    cmd = [
        "enumerate",
        "-z",  # Zoom level...
        str(zoom),  # from 0 to this level, inclusive
        shapes_dir,  # the directory with the input quadtree
    ]
    complete = subprocess.run(cmd, check=True, capture_output=True)

    # Process into a tuple of 4-element tuples (shape_dir, zoom, tile x, tile y)
    output = []
    for line in complete.stdout.decode("utf8").splitlines():
        out = line.split()
        if out:
            assert len(out) == 4
            output.append(tuple(out))
    return tuple(output)


def create_tile_subfolders(tile_params, tiles_dir):
    """Create tile output subfolders if they do not exist."""

    folder_parts = set()
    for source_dir, zoom, tile_x, tile_y in tile_params:
        folder_parts.add((zoom, tile_x))

    for zoom, tile_x in folder_parts:
        folder = os.path.join(tiles_dir, zoom, tile_x)
        os.makedirs(folder, exist_ok=True)


def generate_tile(
    source_dir, zoom, tile_x, tile_y, tiles_dir, extra_args=None, suffix=""
):
    """Generate a space-optimized tile at a given zoom level and position."""
    render_cmd = [
        "render",
        "-B",  # Set basic display parameters...
        "12:0.0379:0.874",  # base zoom (default), brightness, ramp (less than defaults)
        "-c0088FF",  # fully saturated color, blue
        "-t0",  # Fully transparent with no data
        "-O",  # Tune for distance between points...
        "16:1600:1.5",  # Defaults for base, distance, ramp
        "-G",  # Gamma curve...
        "0.5",  # Default of square root
    ]
    if extra_args:
        render_cmd.extend(extra_args)
    render_cmd.extend((source_dir, zoom, tile_x, tile_y))

    pngquant_cmd = [
        "pngquant",
        "--speed",
        "3",  # Default speed
        "--quality",
        "65-95",  # JPEG-style quality, no compress if below 65%, aim for 95%
        "32",  # Output a 32-bit png
    ]

    # Emulate the shell command render | pngquant > out.png
    output_path = os.path.join(tiles_dir, zoom, tile_x, f"{tile_y}{suffix}.png")
    with open(output_path, "wb") as png:
        render = subprocess.Popen(
            render_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        pngquant = subprocess.Popen(
            pngquant_cmd,
            stdin=render.stdout,
            stdout=png,
            stderr=subprocess.DEVNULL,
        )
        render.stdout.close()
        pngquant.wait()


def sync_tiles(
    pool,
    bucket_name,
    tiles_dir,
    max_zoom,
    raven_client,
    bucket_prefix="tiles/",
    progress_seconds=5.0,
    delete_batch_size=100,
):
    """Sync the local tiles to S3 bucket objects."""

    # Get objects currently in the S3 bucket
    with Timer() as obj_timer:
        objects = get_current_objects(bucket_name, bucket_prefix)
    LOG.debug(
        f"Found {len(objects):,} existing tiles in bucket {bucket_name}/{bucket_prefix}"
        f" in {obj_timer.duration_s:0.1f} seconds"
    )

    # Determine what actions we are taking for each
    with Timer() as action_timer:
        actions = get_sync_actions(tiles_dir, objects)
    LOG.debug(
        f"Completed sync plan in {action_timer.duration_s:0.1f} seconds,"
        f" {len(actions['upload']):,} new"
        f" tile{'' if len(actions['upload']) == 1 else 's'} to upload,"
        f" {len(actions['update']):,} changed"
        f" tile{'' if len(actions['update']) == 1 else 's'} to update,"
        f" {len(actions['delete']):,} orphaned"
        f" tile{'' if len(actions['delete']) == 1 else 's'} to delete,"
        f" and {len(actions['none']):,} unchanged"
        f" tile{'' if len(actions['none']) == 1 else 's'}"
    )
    result = {
        "tile_new": 0,
        "tile_changed": 0,
        "tile_deleted": 0,
        "tile_unchanged": len(actions["none"]),
    }

    # Queue the upload actions
    jobs = []
    for path in actions["upload"]:
        jobs.append(
            pool.apply_async(upload_file, (path, bucket_name, bucket_prefix, tiles_dir))
        )
    for path in actions["update"]:
        jobs.append(
            pool.apply_async(update_file, (path, bucket_name, bucket_prefix, tiles_dir))
        )
    total = len(actions["upload"]) + len(actions["update"])

    # Queue the delete actions in batches
    for paths in chunked(actions["delete"], delete_batch_size):
        total += len(paths)
        jobs.append(pool.apply_async(delete_files, (paths, bucket_name, bucket_prefix)))

    # Wait until complete, report progress
    with Timer() as timer:
        last_elapsed = 0.0
        synced_count = 0
        for job in jobs:
            try:
                tile_result, count = job.get()
                result[tile_result] += count
                synced_count += count
            except Exception as e:
                LOG.error(f"Exception while syncing: {e}")
                raven_client.captureException()
                result["tile_failed"] = result.get("tile_failed", 0) + 1
                synced_count += 1  # Could be wrong if bulk deletion fails
            percent = synced_count / total
            if timer.elapsed > (last_elapsed + progress_seconds):
                LOG.debug(
                    f"  Synced {synced_count:,} file{'' if total == 1 else 's'} ({percent:.1%})"
                )
                last_elapsed = timer.elapsed

    return result


def upload_status_file(bucket_name, runtime_data, bucket_prefix="tiles/"):
    """Upload the status file to S3"""

    bucket = s3_bucket(bucket_name)
    obj = bucket.Object(bucket_prefix + "data.json")
    data = {"updated": util.utcnow().isoformat()}
    data.update(runtime_data)
    obj.put(
        Body=dumps(data),
        CacheControl="max-age=3600, public",
        ContentType="application/json",
    )


def s3_bucket(bucket_name):
    """Initialize the s3 bucket client."""
    global S3_BUCKETS
    if S3_BUCKETS is None:
        S3_BUCKETS = {}
    if bucket_name not in S3_BUCKETS:
        S3_BUCKETS[bucket_name] = boto3.resource("s3").Bucket(bucket_name)
    return S3_BUCKETS[bucket_name]


def get_current_objects(bucket_name, bucket_prefix):
    """Get names, sizes, and MD5 signatures of objects in the bucket."""

    bucket = s3_bucket(bucket_name)
    objects = {}
    for obj in bucket.objects.filter(Prefix=bucket_prefix):
        if obj.key.endswith(".png"):
            name = obj.key[len(bucket_prefix) :]
            md5 = obj.e_tag.strip('"')
            objects[name] = (obj.size, md5)

    return objects


def get_sync_actions(tiles_dir, objects):
    """Determine the actions to take to sync tiles with S3 bucket."""
    actions = {
        "upload": [],
        "update": [],
        "delete": [],
        "none": [],
    }
    remaining_objects = set(objects.keys())

    for png in get_png_entries(tiles_dir):
        obj_name = png.path[len(tiles_dir) :].lstrip("/")
        if obj_name in remaining_objects:
            remaining_objects.remove(obj_name)

            # Check if size then md5 are different
            changed = True
            obj_size, obj_md5 = objects[obj_name]
            local_size = png.stat().st_size
            if local_size == obj_size:
                with open(png.path, "rb") as fd:
                    local_md5 = hashlib.md5(fd.read()).hexdigest()
                if local_md5 == obj_md5:
                    changed = False

            if changed:
                actions["update"].append(obj_name)
            else:
                actions["none"].append(obj_name)
        else:
            # New object
            actions["upload"].append(obj_name)

    # Any remaining objects should be deleted
    actions["delete"] = sorted(remaining_objects)
    return actions


def upload_file(path, bucket_name, bucket_prefix, tiles_dir):
    send_file(path, bucket_name, bucket_prefix, tiles_dir)
    return "tile_new", 1


def update_file(path, bucket_name, bucket_prefix, tiles_dir):
    send_file(path, bucket_name, bucket_prefix, tiles_dir)
    return "tile_changed", 1


def send_file(path, bucket_name, bucket_prefix, tiles_dir):
    """Send the local file to the S3 bucket."""

    obj = s3_bucket(bucket_name).Object(bucket_prefix + path)
    local_path = os.path.join(tiles_dir, path)
    obj.upload_file(
        local_path,
        ExtraArgs={
            "CacheControl": "max-age=3600, public",
            "ContentType": "image/png",
        },
    )


def delete_files(paths, bucket_name, bucket_prefix):
    """Delete multiple files from the S3 bucket."""
    delete_request = {
        "Objects": [{"Key": bucket_prefix + path} for path in paths],
        "Quiet": True,
    }
    resp = s3_bucket(bucket_name).delete_objects(Delete=delete_request)
    if resp.get("Errors"):
        raise RuntimeError(f"Error deleting: {resp['Errors']}")
    return "tile_deleted", len(paths)


def get_png_entries(top):
    """Recursively find .png files in a folder"""
    for entry in os.scandir(top):
        if entry.is_dir():
            for subentry in get_png_entries(entry.path):
                yield subentry
        elif entry.name.endswith(".png"):
            yield entry


#
# Command-line entry points
#


def get_parser():
    """Return a command-line parser."""

    try:
        # How many CPUs can this process address?
        # Avaiable on some Unix systems, and in Docker image
        concurrency = len(os.sched_getaffinity(0))
    except AttributeError:
        # Fallback to the CPU count
        concurrency = os.cpu_count()
    parser = argparse.ArgumentParser(description="Generate and upload datamap tiles.")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=(
            "Turn on verbose logging. Equivalent to setting LOCAL_DEV_ENV=1"
            " and LOGGING_LEVEL=debug"
        ),
    )
    parser.add_argument("--create", action="store_true", help="Create tiles")
    parser.add_argument("--upload", action="store_true", help="Upload tiles to S3")
    parser.add_argument(
        "--concurrency",
        type=int,
        choices=list(range(1, concurrency + 1)),
        default=concurrency,
        help=f"How many concurrent processes to use? (default {concurrency})",
    )
    parser.add_argument(
        "--output",
        help=(
            "Directory for generated tiles and working files. A temporary"
            " directory is created and used if omitted."
        ),
    )
    return parser


def check_bucket(bucket_name):
    """
    Check that we can write to a bucket.

    Returns (True, None) on success, (False, "fail message") if not writable

    Bucket existance check based on https://stackoverflow.com/a/47565719/10612
    """
    s3 = boto3.resource("s3")

    # Test if we can see the bucket at all
    try:
        s3.meta.client.head_bucket(Bucket=bucket_name)
    except botocore.exceptions.ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code == 403:
            return False, "Access forbidden"
        elif error_code == 404:
            return False, "Bucket does not exist"
        else:
            msg = (
                "Unknown error on head_bucket,"
                f" Code {e.response['Error']['Code']},"
                f" Message {e.response['Error']['Message']}"
            )
            return False, msg
    except botocore.exceptions.NoCredentialsError:
        return False, (
            "Unable to locate AWS credentials, see "
            "https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html"
        )

    # Create and delete a test file
    bucket = s3_bucket(bucket_name)
    test_name = f"test-{uuid.uuid4()}"
    test_obj = bucket.Object(test_name)
    test_obj.put(Body="test for writability")
    test_obj.wait_until_exists()
    test_obj.delete()

    return True, None


def main(_argv=None, _raven_client=None, _bucket_name=None):
    """
    Command-line entry point.

    :param _argv: Simulated sys.argv[1:] arguments for testing
    :param _raven_client: override Raven client for testing
    :param _bucket_name: override S3 bucket name for testing
    :return: A system exit code
    :rtype: int
    """

    # Parse the command line
    parser = get_parser()
    args = parser.parse_args(_argv)
    create = args.create
    upload = args.upload
    concurrency = args.concurrency
    verbose = args.verbose

    # Setup basic services
    if verbose:
        configure_logging(local_dev_env=True, logging_level="DEBUG")
    else:
        configure_logging()
    raven_client = configure_raven(
        transport="sync", tags={"app": "datamap"}, _client=_raven_client
    )

    # Check consistent output_dir, create, upload
    exit_early = 0
    output_dir = None
    if args.output:
        output_dir = os.path.abspath(args.output)
        tiles_dir = os.path.join(output_dir, "tiles")
        if not create and not os.path.isdir(tiles_dir):
            LOG.error(
                "The tiles subfolder of the --output directory should already"
                " exist when calling --upload without --create, to avoid"
                " deleting files from the S3 bucket.",
                tiles_dir=tiles_dir,
            )
            exit_early = 1
    else:
        if create and not upload:
            LOG.error(
                "The --output argument is required with --create but without"
                " --upload, since the temporary folder is removed at exit."
            )
            exit_early = 1

        if upload and not create:
            LOG.error(
                "The --output argument is required with --upload but without"
                " --create, to avoid deleting all tiles in the S3 bucket."
            )
            exit_early = 1

    # Exit early with help message if error or nothing to do
    if exit_early or not (create or upload):
        parser.print_help()
        return exit_early

    # Determine the S3 bucket name
    bucket_name = _bucket_name
    if not _bucket_name:
        bucket_name = settings("asset_bucket")
        if bucket_name:
            bucket_name = bucket_name.strip("/")

    # Check that the implied credentials are authorized to use the bucket
    if upload:
        if not bucket_name:
            LOG.error("Unable to determine upload bucket_name.")
            return 1
        else:
            works, fail_msg = check_bucket(bucket_name)
            if not works:
                LOG.error(
                    f"Bucket {bucket_name} can not be used for uploads: {fail_msg}"
                )
                return 1

    # Generate and upload the tiles
    success = True
    result = {}
    try:
        with Timer() as timer:
            if output_dir:
                result = generate(
                    output_dir,
                    bucket_name,
                    raven_client,
                    create=create,
                    upload=upload,
                    concurrency=concurrency,
                )
            else:
                with util.selfdestruct_tempdir() as temp_dir:
                    result = generate(
                        temp_dir,
                        bucket_name,
                        raven_client,
                        create=create,
                        upload=upload,
                        concurrency=concurrency,
                    )
    except Exception:
        raven_client.captureException()
        success = False
        raise
    finally:
        if create and upload:
            task = "generation and upload"
        elif create:
            task = "generation"
        else:
            task = "upload"
        if success:
            complete = "complete"
        else:
            complete = "failed"
        final_log = structlog.get_logger("canonical-log-line")
        final_log.info(
            f"Datamap tile {task} {complete} in {timer.duration_s:0.1f} seconds.",
            success=success,
            duration_s=timer.duration_s,
            script_name="ichnaea.scripts.datamap",
            create=create,
            upload=upload,
            concurrency=concurrency,
            bucket_name=bucket_name,
            **result,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
