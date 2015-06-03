from ichnaea.constants import DEGREE_DECIMAL_PLACES
from ichnaea.geocalc import distance


class Location(object):
    """A location returned by a location provider."""

    def __init__(self, accuracy=None, country_code=None, country_name=None,
                 fallback=None, lat=None, lon=None, query_data=True,
                 source=None):
        self.accuracy = self._round(accuracy)
        self.country_code = country_code
        self.country_name = country_name
        self.fallback = fallback
        self.lat = self._round(lat)
        self.lon = self._round(lon)
        self.query_data = query_data
        self.source = source

    def _round(self, value):
        if value is not None:
            value = round(value, DEGREE_DECIMAL_PLACES)
        return value

    def found(self):  # pragma: no cover
        """Does this location include any data?"""
        raise NotImplementedError

    def agrees_with(self, other):  # pragma: no cover
        """Does this location match the other location?"""
        raise NotImplementedError

    def accurate_enough(self):  # pragma: no cover
        """Is this location accurate enough to return it?"""
        raise NotImplementedError

    def more_accurate(self, other):  # pragma: no cover
        """Is this location better than the passed in location?"""
        raise NotImplementedError


class EmptyLocation(Location):
    """An undefined location."""

    def found(self):
        return False

    def agrees_with(self, other):  # pragma: no cover
        return True

    def accurate_enough(self):
        return False

    def more_accurate(self, other):  # pragma: no cover
        return False


class Position(Location):
    """The position returned by a position query."""

    def __repr__(self):  # pragma: no cover
        return 'Position<lat: {lat}, lon: {lon}, accuracy: {accuracy}>'.format(
            lat=self.lat,
            lon=self.lon,
            accuracy=self.accuracy,
        )

    def found(self):
        return None not in (self.lat, self.lon)

    def agrees_with(self, other):
        dist = distance(other.lat, other.lon, self.lat, self.lon) * 1000
        return dist <= other.accuracy

    def accurate_enough(self):
        # For position data we currently always want to continue.
        return False

    def more_accurate(self, other):
        """
        Are we more accurate than the passed in other position and fit into
        the other's position range?
        """
        if not self.found():
            return False
        if not other.found():
            return True
        if self.source < other.source:
            return True
        return (self.agrees_with(other) and self.accuracy < other.accuracy)


class Country(Location):
    """The country returned by a country query."""

    def __repr__(self):  # pragma: no cover
        return 'Country<name: {name}, code: {code}>'.format(
            name=self.country_name,
            code=self.country_code,
        )

    def found(self):
        return None not in (self.country_code, self.country_name)

    def agrees_with(self, other):
        return self.country_code == other.country_code

    def accurate_enough(self):
        return self.found()

    def more_accurate(self, other):
        if not self.found():
            return False
        if not other.found():
            return True
        if self.source < other.source:
            return True
        return False
