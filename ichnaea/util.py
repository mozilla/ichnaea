from datetime import datetime
import zlib

from pytz import UTC
from webob.response import gzip_app_iter


def encode_gzip(data):
    # based on webob.response.Response.encode_content
    return ''.join(gzip_app_iter(data))


def decode_gzip(data):
    # based on webob.response.Response.decode_content
    return zlib.decompress(data, 16 + zlib.MAX_WBITS)


def utcnow():
    return datetime.utcnow().replace(microsecond=0, tzinfo=UTC)
