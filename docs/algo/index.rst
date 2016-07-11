.. _algo:

==========
Algorithms
==========

The project uses a couple of different approaches and algorithms.

There's two general approaches to calculate positions from signal sources,
without the cooperation of the signal sources or mobile networks.

1. Determine the location of signal sources from :term:`observations`,
   then compare / trilaterate user locations.

2. Generate signal fingerprints for a fine-grained grid of the world.
   Find best match for a observed fingerprint.

The second approach has a much better accuracy, but relies on a lot more
available and constantly updated data. For most of the world this
approach is not practical, so we currently focus on approach one.

In theory one would assume that one could use signal strength data to
infer a distance measure from it. The further a device is away from the
signal source, the weaker the signal should get.

Unfortunately the signal strength is more dependent on the device type,
how a user holds a device and changing environmental factors like trucks in
the way. Even worse modern networks adjust their signal strength to the number
of devices inside their reception area. This makes this data highly
unreliable while looking up a user's position via a single reading.

In aggregate over many data points this information can still be valuable
in determining the actual position of the signal source. While observing
multiple signals at once, their relative strengths can also be used, as
this keeps some of the changing factors constant, like the device type.

One other approach is using time of flight data as a distance metric.
While there are some reflection and multipath problems, it's a much more
accurate distance predictor. Fine grained enough timing data is
unfortunately almost never available to the application or operating
system layer in client devices. Some LTE networks and really modern
WiFi networks with support for 802.11v are the rare exception to this.
But these are so rare, that we currently ignore timing data.


.. toctree::
   :maxdepth: 2

   accuracy
