# Disable deprecation warnings in production mode
import warnings

from shapely import speedups

warnings.simplefilter('ignore', DeprecationWarning)
warnings.simplefilter('ignore', PendingDeprecationWarning)

# Enable shapely speedups
if speedups.available:
    speedups.enable()
del speedups
