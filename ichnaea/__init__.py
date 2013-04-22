import logging

from ichnaea.app import main  # NOQA

logger = logging.getLogger('ichnaea')

__all__ = ('logger', 'main')
