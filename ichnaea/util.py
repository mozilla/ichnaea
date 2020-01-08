from contextlib import contextmanager
from datetime import datetime
import gzip
from io import BytesIO
from itertools import zip_longest
import json
import os
import shutil
import struct
import sys
import tempfile
import zlib

from pytz import UTC

from ichnaea.exceptions import GZIPDecodeError

HERE = os.path.dirname(__file__)
APP_ROOT = os.path.dirname(HERE)


@contextmanager
def gzip_open(filename, mode, compresslevel=6):
    """Open a gzip file.

    :param mode: Either `r` or `w` for read or write access.
    """
    with open(filename, mode + "b") as fd:
        with gzip.open(
            fd, mode=mode + "t", compresslevel=compresslevel, encoding="utf-8"
        ) as gzip_file:
            yield gzip_file


def encode_gzip(data, compresslevel=6):
    """Encode the passed in data with gzip."""
    out = BytesIO()
    with gzip.GzipFile(
        None, "wb", compresslevel=compresslevel, fileobj=out
    ) as gzip_file:
        gzip_file.write(data)
    return out.getvalue()


def decode_gzip(data):
    """Return the gzip-decompressed bytes.

    :raises: :exc:`~ichnaea.exceptions.GZIPDecodeError`
    """
    try:
        with gzip.GzipFile(None, mode="rb", fileobj=BytesIO(data)) as gzip_file:
            out = gzip_file.read()
        return out
    except (IOError, OSError, EOFError, struct.error, zlib.error) as exc:
        raise GZIPDecodeError(repr(exc))


@contextmanager
def selfdestruct_tempdir():
    base_path = tempfile.mkdtemp()
    try:
        yield base_path
    finally:
        shutil.rmtree(base_path)


def utcnow():
    """Return the current time in UTC with a UTC timezone set."""
    return datetime.utcnow().replace(microsecond=0, tzinfo=UTC)


def version_info():
    """Return version.json information."""
    version_file = os.path.join(APP_ROOT, "version.json")
    info = {}
    if os.path.exists(version_file):
        with open(version_file, "r") as fp:
            try:
                info = json.load(fp)
            except json.JsonDecodeException:
                pass
    return info


def contribute_info():
    """Return contribute.json information."""
    contribute_file = os.path.join(APP_ROOT, "contribute.json")
    if os.path.exists(contribute_file):
        with open(contribute_file, "r") as fp:
            try:
                return json.load(fp)
            except json.JsonDecodeException:
                pass
    return {}


def print_table(table, delimiter=" | ", stream_write=sys.stdout.write):
    """Takes a list of lists and prints a table to stdout.

    :arg list-of-lists table: the table to print out
    :arg str delimiter: the delimiter between fields in a row
    :arg writer stream_write: the ``write`` of a file-like object

    """
    # Find the max size value for each column
    col_maxes = [0] * len(table[0])
    for row in table:
        col_maxes = [
            max(len(str(field)), col_max)
            for field, col_max in zip_longest(row, col_maxes, fillvalue=0)
        ]

    for row in table:
        stream_write(
            delimiter.join(
                [
                    str(field).ljust(col_max)
                    for field, col_max in zip_longest(row, col_maxes, fillvalue="")
                ]
            )
            + "\n"
        )
