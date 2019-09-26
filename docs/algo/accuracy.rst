.. _accuracy:

========
Accuracy
========

Depending on the signal standard, we can promise different levels of accuracy.

Underlying this is the assumption that we have enough data about the area.
Without enough data, Ichnaea will fall back to less accurate data sources
depending on the configuration.

Bluetooth is the most accurate, followed by WiFi, and than cell based
estimation using single cells, multiple cells, or cell location areas. GeoIP
serves as a general fallback.


Bluetooth / WiFi
----------------

Bluetooth and WiFi networks have a fairly limited range. Bluetooth low-energy
beacons typically reach just a couple meters and WiFi networks reach up to 100
meters. With obstacles like walls and people in the way, these distances get
even lower.

However, this data can be skewed when the device in question is moving. It
takes some time to do a network scan and devices tend to cache this information
heavily. There can be a time delta of tens of seconds between when a network
was actually seen and when it is reported to the application layer. With a fast
moving device this can lead to inaccuracies of a couple kilometers. WiFi
networks tend to show up in scans long after they are out of reach, especially
if the the device was actually connected to these networks.

This means position estimates based on WiFi networks are usually accurate to
100 meters. If a lot of networks are available in the area, accuracy tends to
increase to about 10 or 20 meters. Bluetooth networks tend to be accurate to
about 10 meters.

One difficult challenge with Bluetooth and WiFi networks are the constantly
moving networks. For example, WiFi networks installed on buses or trains or in
the form of hotspot-enabled mobile phones or tablets. Detecting movement and
inconsistencies between observed data and the database world view are
important.


GSM Cells
---------

In GSM networks, one typically only has access to the unique cell id of the
serving cell. In GSM networks, the phone does not know the full cell ids of any
neighboring cells unless it associates with the new cell as part of a hand-over
and forgets the cell id of the old cell.

So we're limited to a basic :term:`Cell-ID` approach where we assume that the
user is at the center of the current GSM cell area and we use the cell radius
as the accuracy.

GSM cells are restricted to a maximum range of 35km, but there are rare
exceptions using the GSM extended range of 120km.

In more populated places the cell sizes are typically much smaller, but
accuracy will be in the range of tens of kilometers.

WCDMA Cells
-----------

In WCDMA networks, neighboring cell information can be available. However,
limitations in chipset drivers, the radio interface layer, and the operating
systems often hide this data from application code or only partially expose the
cell identifiers. For example, they might only expose the carrier and primary
scrambling code of the neighboring cells.

In most cases we are limited to the same approach as for GSM cells. In urban
areas, the typical sizes of WCDMA cells are much smaller than GSM cells. This
leads to improved accuracy in the range of 1 to 10 kilometers. However in rural
areas, WCDMA cells can be larger than GSM cells, sometimes as large as 60 to 70
kilometers.

LTE Cells
---------

LTE networks are similar to WCDMA networks and the same restrictions on
neighboring cells applies. Instead of a primary scrambling code, LTE uses a
physical cell id which for our purposes has similar characteristics.

LTE cells are often smaller than WCDMA cells which leads to better accuracies.

LTE networks also expose a time-based distance metric in the form of the timing
advance. While we currently don't use this information, it has the potential to
significantly improve position estimates based on multiple cells.

GeoIP
-----

The accuracy of GeoIP depends on the region the user is in. In the US, GeoIP
can be fairly accurate and often places the user in the right city or
metropolitan area. In many other parts of the world, GeoIP is only accurate to
the region level.

Typical GeoIP accuracies are either in the 25 km range for city based estimates
or multiple hundred kilometers for region based estimates.

IPv6 has the chance to improve this situation, as the need for private carrier
networks and network address translation decreases. So far this hasn't made any
measurable impact and most traffic is still restricted to IPv4.
