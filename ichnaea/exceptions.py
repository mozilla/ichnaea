"""
Base classes for ichnaea specific exceptions, primarily used in deciding
what exceptions and stats to log on a per request basis.
"""


class BaseClientError(Exception):
    """Base class for client errors.
    """


class BaseServiceError(Exception):
    """Base class service errors.
    """
