import unittest

from ichnaea.geocalc import distance


class TestDistance(unittest.TestCase):

    def test_simple_distance(self):
        # This is a simple case where the points are close to each other.

        lat1 = 44.0337065
        lon1 = -79.4908184
        lat2 = 44.0347065
        lon2 = -79.4918184
        delta = distance(lat1, lon1, lat2, lon2)
        sdelta = "%0.4f" % delta
        self.assertEqual(sdelta, '0.1369')

    def test_antipodal(self):
        # Antipodal points (opposite sides of the planet) have a round off
        # error with the standard haversine calculation which is extremely
        # old and assumes we are using fixed precision math instead of IEEE
        # floats.

        lat1 = 90.0
        lon1 = 0.0
        lat2 = -90.0
        lon2 = 0
        delta = distance(lat1, lon1, lat2, lon2)
        sdelta = "%0.4f" % delta
        self.assertEqual(sdelta, '20015.0868')

    def test_out_of_range(self):
        # We don't always sanitize the incoming data and thus have to deal
        # with some invalid coordinates. Make sure the distance function
        # doesn't error out on us.

        lat1 = -100.0
        lon1 = -186.0
        lat2 = 0.0
        lon2 = 0.0
        delta = distance(lat1, lon1, lat2, lon2)
        sdelta = "%0.4f" % delta
        self.assertEqual(sdelta, '8901.7476')
