from ichnaea.constants import DEGREE_DECIMAL_PLACES
from ichnaea.geocalc import distance


class Location(object):
    """A location returned by a location provider."""

    def __init__(self, source=None,
                 lat=None, lon=None, accuracy=None,
                 country_code=None, country_name=None, query_data=True):
        self.source = source
        self.lat = self._round(lat)
        self.lon = self._round(lon)
        self.accuracy = self._round(accuracy)
        self.country_code = country_code
        self.country_name = country_name
        self.query_data = query_data

    def _round(self, value):
        if value is not None:
            value = round(value, DEGREE_DECIMAL_PLACES)
        return value

    def found(self):  # pragma: no cover
        """Does this location include any location data?"""
        raise NotImplementedError

    def agrees_with(self, other_location):  # pragma: no cover
        """Does this location match the position of the other location?"""
        raise NotImplementedError

    def accurate_enough(self):  # pragma: no cover
        """Is this location accurate enough to return it?"""
        raise NotImplementedError

    def more_accurate(self, other_location):  # pragma: no cover
        """Is this location better than the passed in location?"""
        raise NotImplementedError


class EmptyLocation(Location):
    """An undefined location."""

    def found(self):
        return False

    def agrees_with(self, other_location):  # pragma: no cover
        return True

    def accurate_enough(self):
        return False

    def more_accurate(self, other_location):  # pragma: no cover
        return False


class PositionLocation(Location):
    """The location returned by a position query."""

    def found(self):
        return None not in (self.lat, self.lon)

    def agrees_with(self, other_location):
        dist = distance(
            other_location.lat, other_location.lon, self.lat, self.lon) * 1000
        return dist <= other_location.accuracy

    def accurate_enough(self):
        # For position data we currently always want to continue.
        return False

    def more_accurate(self, other_location):
        """
        Are we more accurate than the passed in other_location and fit into
        the other_location's range?
        """
        if not self.found():
            return False
        if not other_location.found():
            return True
        if self.source < other_location.source:
            return True
        return (
            self.agrees_with(other_location) and
            self.accuracy < other_location.accuracy)


class CountryLocation(Location):
    """The location returned by a country query."""

    def found(self):
        return None not in (self.country_code,  self.country_name)

    def agrees_with(self, other_location):  # pragma: no cover
        return self.country_code == other_location.country_code

    def accurate_enough(self):
        return self.found()

    def more_accurate(self, other_location):
        if not self.found():
            return False
        if not other_location.found():
            return True
        if self.source < other_location.source:  # pragma: no cover
            return True
        return False  # pragma: no cover
