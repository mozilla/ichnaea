"""Generally useful helper functionality."""
from contextlib import contextmanager
from datetime import datetime
import gzip
from io import BytesIO
import shutil
import struct
import sys
import tempfile
import zlib

from pytz import UTC
import six

from ichnaea.exceptions import GZIPDecodeError

if sys.version_info < (2, 7):  # pragma: no cover

    # the io module was pure-python in 2.6, use a C version
    from cStringIO import StringIO as BytesIO  # NOQA

    class GzipFile(gzip.GzipFile):  # NOQA
        # Python 2.6 GzipFile isn't a context manager

        # Add a default value, as this is used in the __repr__ and only
        # set in the __init__ on successfully opening the file. Sentry/raven
        # would bark on this while trying to capture the stack frame locals.
        fileobj = None

        @property
        def closed(self):  # pragma: no cover
            return self.fileobj is None

        def __enter__(self):
            if self.fileobj is None:  # pragma: no cover
                raise ValueError('I/O operation on closed GzipFile object')
            return self

        def __exit__(self, *args):
            self.close()

else:  # pragma: no cover
    GzipFile = gzip.GzipFile


@contextmanager
def gzip_open(filename, mode, compresslevel=6):  # pragma: no cover
    """Open a gzip file with an API consistent across Python 2/3.

    :param mode: Either `r` or `w` for read or write access.
    """
    # open with either mode r or w
    if six.PY2:
        with GzipFile(filename, mode,
                      compresslevel=compresslevel) as gzip_file:
            yield gzip_file
    else:
        with open(filename, mode + 'b') as fd:
            with gzip.open(fd, mode=mode + 't',
                           compresslevel=compresslevel,
                           encoding='utf-8') as gzip_file:
                yield gzip_file


def encode_gzip(data, compresslevel=6, encoding='utf-8'):
    """Encode the passed in data with gzip."""
    if isinstance(data, six.string_types):
        data = data.encode(encoding)
    out = BytesIO()
    with GzipFile(None, 'wb',
                  compresslevel=compresslevel, fileobj=out) as gzip_file:
        gzip_file.write(data)
    return out.getvalue()


def decode_gzip(data, encoding='utf-8'):
    """Decode the bytes data and return a Unicode string.

    :raises: :exc:`~ichnaea.exceptions.GZIPDecodeError`
    """
    try:
        with GzipFile(None, mode='rb', fileobj=BytesIO(data)) as gzip_file:
            out = gzip_file.read()
        return out.decode(encoding)
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
