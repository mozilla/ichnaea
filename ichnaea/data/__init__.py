"""
Contains asynchronous tasks and data pipeline logic.
"""

from ichnaea import conf


def _cell_export_enabled():
    return bool(conf.ASSET_BUCKET)


def _web_content_enabled():
    return bool(conf.MAP_TOKEN)
