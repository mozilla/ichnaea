.. _calculation:

===========
Calculation
===========

There's two general approaches to calculate positions from signal sources,
without the cooperation of the signal sources or mobile networks.

1. Determine the location of signal sources from measurements, then
   compare / trilaterate user locations.

2. Generate signal fingerprints for a fine-grained grid of the world.
   Find best match for a observed fingerprint.

The second approach has a much better accuracy, but relies on a lot more
available data. It is able to compensate for all the attenuation loss and
multipath problems inherent to using signal strength or time of flight to
calculate distances.

Since we start out with little data, we'll use approach number one at first.

Most devices only give us access to coarse grained signal strength measures
like the ASU. If available we try to record and use more accurate time of
flight (or time of arrival) measures. Upcoming standards like 802.11v should
improve the situation for Wifi networks.

Accuracy
========

Depending on the signal standard, we can promise different sorts of accuracy.

GSM
---

For GSM networks, we will likely have access to unique cell ids and ASU or RSSI
measurements.

The ASU has 32 different values and a GSM cell covers 35km or 120km with
extended range. The RSSI has 62 different values.

Worst case:

- ASU==0 or RSI==-113: This could be an extended range cell, so 120km accuracy.

Best case:

- RSSI=-51: 550m accuracy
- ASU==31: 1100m accuracy

Ignoring any attenuation loss, each ASU/RSSI step represents another 1100/550m
in distance. Unfortunately attenuation loss is very real and severe and can
completely block any signal, so these accuracies are very brittle.

If we get access to GSM timing advance data, we have 64 possible values, with
the same extended range cell caveat. Otherwise each step represent 550m. The
chance of multipath problems is much less, and we can likely assume that the
TA value is just off by one.

UMTS
----

* todo

CDMA
----

* oh fun, RSSI represents combined signal strength from all towers :(

LTE
---

* todo

WiFi
----

* todo
