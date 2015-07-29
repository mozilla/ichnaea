"""Generally useful helper functionality."""
from contextlib import contextmanager
from datetime import datetime
import gzip
from io import BytesIO
import sys

from pytz import UTC
import six

if sys.version_info < (2, 7):  # pragma: no cover

    # the io module was pure-python in 2.6, use a C version
    from cStringIO import StringIO as BytesIO  # NOQA

    class GzipFile(gzip.GzipFile):  # NOQA
        # Python 2.6 GzipFile isn't a context manager

        # Add a default value, as this is used in the __repr__ and only
        # set in the __init__ on successfully opening the file. Sentry/raven
        # would bark on this while trying to capture the stack frame locals.
        fileobj = None

        def __enter__(self):
            if self.fileobj is None:  # pragma: no cover
                raise ValueError('I/O operation on closed GzipFile object')
            return self

        def __exit__(self, *args):
            self.close()

else:  # pragma: no cover
    GzipFile = gzip.GzipFile


@contextmanager
def gzip_open(filename, mode):  # pragma: no cover
    """Open a gzip file with an API consistent across Python 2/3.

    :param mode: Either `r` or `w` for read or write access.
    """
    # open with either mode r or w
    if six.PY2:
        yield GzipFile(filename, mode)
    else:
        with open(filename, mode + 'b') as fd:
            yield gzip.open(fd, mode=mode + 't', encoding='utf-8')


def encode_gzip(data, encoding='utf-8'):
    """Encode the passed in data with gzip."""
    if isinstance(data, six.string_types):
        data = data.encode(encoding)
    out = BytesIO()
    with GzipFile(None, 'wb', compresslevel=9, fileobj=out) as gzip_file:
        gzip_file.write(data)
    return out.getvalue()


def decode_gzip(data, encoding='utf-8'):
    """Decode the bytes data and return a Unicode string.

    :raises: OSError
    """
    try:
        with GzipFile(None, mode='rb', fileobj=BytesIO(data)) as gzip_file:
            out = gzip_file.read()
        return out.decode(encoding)
    except (IOError, OSError) as exc:
        raise OSError(str(exc))


def utcnow():
    """Return the current time in UTC with a UTC timezone set."""
    return datetime.utcnow().replace(microsecond=0, tzinfo=UTC)
