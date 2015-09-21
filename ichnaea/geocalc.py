"""
Contains helper functions for various geo related calculations.
"""

import numpy

from ichnaea import _geocalc


def aggregate_position(circles, minimum_accuracy):
    """
    Calculate the aggregate position based on a number of circles
    (numpy 3-column arrays of lat/lon/radius).

    Return the position and an accuracy estimate, but at least
    use the minimum_accuracy.
    """
    if len(circles) == 1:
        return (float(circles[0][0]),
                float(circles[0][1]),
                max(float(circles[0][2]), minimum_accuracy))

    points, _ = numpy.hsplit(circles, [2])
    lat, lon = _geocalc.centroid(points)

    # Bad approximation. This one takes the maximum distance from
    # the centroid to any of the provided circle centers.
    # It ignores the radius of those circles.
    radius = _geocalc.max_distance(lat, lon, points)
    return (lat, lon, max(radius, minimum_accuracy))


def circle_radius(lat, lon, max_lat, max_lon, min_lat, min_lon):
    """
    Compute the maximum distance, in meters, from a (lat, lon) point
    to any of the extreme points of a bounding box.
    """
    points = numpy.array([
        (min_lat, min_lon),
        (min_lat, max_lon),
        (max_lat, min_lon),
        (max_lat, max_lon),
    ], dtype=numpy.double)

    radius = _geocalc.max_distance(lat, lon, points)
    return int(round(radius))
