from ichnaea.geocalc import distance


def test_simple_distance():
    """
    This is a simple case where the points are close to each other.
    """
    lat1 = 44.0337065
    lon1 = -79.4908184
    lat2 = 44.0347065
    lon2 = -79.4918184
    delta = distance(lat1, lon1, lat2, lon2)
    sdelta = "%0.4f" % delta
    assert sdelta == '0.1369'

def test_antipodal():
    """
    Antipodal points (opposite sides of the planet) have a round off
    error with the standard haversine calculation.
    """
    lat1 = 90.0
    lon1 = 0.0
    lat2 = -90.0
    lon2 = 0
    delta = distance(lat1, lon1, lat2, lon2)
    sdelta = "%0.4f" % delta
    # TODO: add haversine error check here
    assert sdelta == '20015.0868'
