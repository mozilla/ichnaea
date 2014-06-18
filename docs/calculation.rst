.. _calculation:

===========
Calculation
===========

There's two general approaches to calculate positions from signal sources,
without the cooperation of the signal sources or mobile networks.

1. Determine the location of signal sources from observations, then
   compare / trilaterate user locations.

2. Generate signal fingerprints for a fine-grained grid of the world.
   Find best match for a observed fingerprint.

The second approach has a much better accuracy, but relies on a lot more
available and constantly updated data. For most of the world this
approach is not practical, so we currently focus on approach one.

In theory one would assume that one could use signal strength data to
infer a distance measure from it. The further a device is away from the
signal source, the weaker the signal should get.

Unfortunately the signal strength is more dependent on the device type,
how a user holds a device, changing environmental factors like trucks in
the way. Or modern networks adjust their signal strength to the number
of devices inside their reception area. This makes this data practically
useless while looking up a users position via a single reading.

In aggregate over many data points this information can still be valuable
in determining the actual position of the signal source. While observing
multiple signals at once, their relative strengths can also be used, as
this keeps some of the changing factors constant, like the device type.

One other approach is using time of flight data as a distance metric.
While there are some reflection and multipath problems it's a much more
accurate distance predictor. Fine grained enough timing data is
unfortunately almost never available to the application or operating
system layer in client devices. Some LTE networks and really modern
WiFi networks with support for 802.11v are the rare exception to this.
But these are so rare, that we currently ignore timing data.

Accuracy
========

Depending on the signal standard, we can promise different sorts of accuracy.

Underlying this is the assumption that we have enough data about the
area at all. With no or too little data we'll have to fallback to less
accurate data sources. WiFi is the most accurate, followed by cell based
estimation using single cells, multiple cells or cell location areas.
If all else fails GeoIP serves as a general fallback.

WiFi
----

WiFi networks have a fairly limited range, with buildings in the way often
only in the tens or low hundreds of meters. This means position estimates
based on WiFi networks are usually accurate to 100 meter or slightly more
based on our data and will improve in the future to tens of meters.

In WiFi networks the devices can also almost always see multiple WiFi
networks at once, so trilateration is often available further improving
the position estimate.

One challenge that's particular severe in WiFi networks are all the
constantly moving WiFi networks, for example those installed on buses
or trains or in the form of hotspot enabled mobile phones or tablets.
So movement detection and detecting inconsistencies between observed
data and the database world view are important considerations.

GSM
---

For GSM networks we will likely have access to the unique cell id of the
serving cell only. In GSM networks the phone does not know the full cell
ids of any neighboring cells, unless it associates with the new cell as
part of a hand-over, forgetting the cell id of the old cell.

So we are limited to a basic Cell-ID approach, meaning we assume that the
user is at the center of the current GSM cell area and use the cell radius
as the accuracy.

GSM cells are restricted to a maximum range of 35km, but there are rare
exceptions using the GSM extended range of 120km.

In more populated places the cell sizes are typically much smaller.

UMTS
----

In UMTS networks neighboring cell information can be available. But
limitations in chipset drivers, the radio interface layer and the
operating systems often hide this data from application code. Or
only partially expose the cell identifiers, for example only exposing
the carrier and primary scrambling code of the neighboring cells.

So in most cases we are limited to the same approach as for GSM cells.
The typical cell sizes of UMTS cells are much smaller, which practically
leads to a better accuracy. But UMTS cells in rural areas can have a
larger radius than GSM cells and we observed cells sizes of 60-70km.

LTE
---

LTE networks are similar to UMTS networks and the same restriction on
neighboring cells applies. Instead of a primary scrambling code LTE uses
a physical cell id, which for our purposes has similar characteristics.

LTE cells are again often even smaller than UMTS cells which leads to
better accuracies.

LTE networks also expose a time based distance metric in the form of
the timing advance. While we currently don't use this information, in
the future it has the potential to significantly improve position
estimates based on multiple cells.

CDMA
----

CDMA networks are structured differently from the GSM family. A device
is usually always connected to multiple cell towers at once and
information about signal quality refers to the combined signal quality
gotten from all connected towers.

This means we usually get information about multiple cells and can do
trilateration, leading to better position estimates. Cells sizes are
comparable to UMTS networks and can be in the 100km range in rural
areas.

In theory in CDMA networks the latitude and longitude of each connected
cell tower is sent along to the client device, similar to how it sends
accurate time data. In practice almost none of the cell towers are
configured with this information or it is outdated or outright wrong.
So we don't attempt to use this data.

GeoIP
-----

The accuracy of GeoIP depends a lot on the country or region the user
is in. In the US GeoIP can be fairly accurate and often places the
user in the right city or metropolitan area. In many other parts of
the world GeoIP is only accurate to the country level.

IP version 6 has the chance to improve this situation, as the need for
private carrier networks and network address translation decreases.
But so far this hasn't made any measurable impact and most traffic
is still restricted to IP version 4.
