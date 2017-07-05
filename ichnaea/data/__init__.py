"""
Contains asynchronous tasks and data pipeline logic.
"""

from ichnaea import config


def _cell_export_enabled():
    return bool(config.ASSET_BUCKET)


def _web_content_enabled():
    return bool(config.MAP_TOKEN)
