"""
Contains asynchronous tasks and data pipeline logic.
"""

from ichnaea.conf import settings


def _cell_export_enabled():
    return bool(settings("asset_bucket"))


def _map_content_enabled():
    return bool(settings("mapbox_token"))
