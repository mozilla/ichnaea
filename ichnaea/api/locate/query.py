"""
Code representing a location query.
"""


class Query(object):

    def __init__(self, geoip=None, cell=None, wifi=None, fallbacks=None):
        """
        A class representing a concrete location query.

        :param geoip: An IP address, e.g. 127.0.0.1.
        :type geoip: str

        :param cell: A list of cell query dicts.
        :type cell: list

        :param wifi: A list of wifi query dicts.
        :type wifi: list

        :param fallbacks: A dictionary of fallback options.
        :type fallbacks: dict
        """
        if not geoip:
            geoip = None
        self.geoip = geoip
        if not cell:
            cell = []
        self.cell = cell
        if not wifi:
            wifi = []
        self.wifi = wifi
        if not fallbacks:
            fallbacks = {}
        self.fallbacks = fallbacks
