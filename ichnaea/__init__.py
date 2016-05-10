# Disable deprecation warnings in production mode
import os.path
import sys
import warnings

from shapely import speedups

warnings.simplefilter('ignore', DeprecationWarning)
warnings.simplefilter('ignore', PendingDeprecationWarning)

# Enable shapely speedups
if speedups.available:
    speedups.enable()
del speedups

# Enable pyopenssl based SSL stack
if sys.version_info < (3, 0):  # pragma: no cover
    from requests.packages.urllib3.contrib import pyopenssl
    pyopenssl.inject_into_urllib3()
    del pyopenssl

ROOT = os.path.abspath(os.path.dirname(__file__))

__all__ = (ROOT, )
