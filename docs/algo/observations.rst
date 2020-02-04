.. _observations:

============
Observations
============

Ichnaea builds its database of Bluetooth, WiFi, and Cell stations based on
observations of those stations. The goal is not to identify the position of
the station, but to identify where the station is likely to be observed.

Depending on the observation quality, the station updating algorithm can
confirm a station is active, adjust the position estimate, block it temporarily
from location queries, or remove historic position data completely.

.. contents::
   :local:

The Station Model
=================

A station, regardless of type, is modeled as a circle, where the center is the
weighted average position of observations, and the radius is large enough to
contain historical observations.  A model can be composed of observations from
location queries, giving an estimated position and region for the station, but
keeping it from being using in location queries. A model can instead be
composed of observations based on submission reports, which include a position
from GPS or another source. These stations can be used to help estimate
position for location queries.

.. Source document:
.. https://docs.google.com/drawings/d/1E_QK-NEgB4PkovPjWdWZHNQjm60ed2PAZyZyYkPb9iQ

.. figure:: observations-model.png
    :width: 360px
    :height: 360px
    :align: center
    :alt: A station model, with a weight of 12.5, a box containing historical
          observations, and a circle with a radius that contains the historical
          observations.

New observations are matched to the existing model.  If the observations match
the model type (for example, GPS submissions for a GPS-based model), then they
can update the model's position and radius.

.. Source document:
.. https://docs.google.com/drawings/d/1bIxj9NZHmYYw_W0nmCBRKef2Ze6ee-PYiKBr6J2buNw

.. figure:: observations-model-new-obs.png
    :width: 360px
    :height: 360px
    :align: center
    :alt: Seven new observations of a station, two outside of the bounding box
          and one outside of the bounding radius.

The new observations are weighted by features like accuracy, age, speed, and
signal strength. Some observations have a weight of 0, and are discarded.

.. Source document:
.. https://docs.google.com/drawings/d/1GHCFCt9rf1smZxN_TpqcnVnL_z5fYxEvQcZoYdLxnBQ

.. figure:: observations-model-weighted.png
    :width: 360px
    :height: 360px
    :align: center
    :alt: After weighting, two observations are eliminated, one has a weight
          of 2.0, four have weights less than 1.

The station's position is adjusted by the new observations, and the station
weight is increased. Stations with many observations have a large weight, so
new observations have a diminishing impact on the station position.

To complete the update, the observation bounding box is expanded, if
needed, to enclose the new observations. The radius is adjusted for the
new center and bounding box.

.. Source document:
.. https://docs.google.com/drawings/d/12DL83yvTPUMt3gNEca9qP9kr-sSxyY7XcJjMxaTBxWA

.. figure:: observations-model-update.png
    :width: 360px
    :height: 360px
    :align: center
    :alt: The updated model is overlaid on the ghost of the previous model. The
          center has moved down and to the left, closer to the new observations.
          The bounding box has expanded up and left, and the radius has
          increased to the new box extent.


Modeling WiFi and Cell Stations
===============================

The station model tracks where the station is observed, and does not attempt to
determine where the emitter is located.

For example, a WiFi router may physically be located inside a building, to
maximize the signal for the people in the building. However, people on the
sidewalk or road outside the building are more likely to observe the WiFi
router at the same time they have a good GPS or other GNSS position lock. The
WiFi station model will be weighted toward the outside observations, and may
show a position outside of the building.

.. Source document:
.. https://docs.google.com/drawings/d/1E7YbqdUcBW3yzGTdl-4RXzZ-0AFmVTaT_7CqxLytWnQ

.. figure:: observations-wifi.png
    :width: 480px
    :height: 480px
    :scale: 50%
    :align: center
    :alt: A wifi router in a building has some observations inside the
          building, but the majority are from the sidewalk and the street
          outside, so the station model locates the station just outside the
          building.

Cell signals are directional, transmitting in an arc or wedge rather than
in all directions. They are often observed by phones in vehicles, such as
when following directions from a map application.

In a city, the station model will encompass the service area, biased toward
observations on roads. The cell emitter will often be outside of the model
radius.

.. Source:
.. https://docs.google.com/drawings/d/1oNnlLREgv8NGdPIk3EjwdAPF_3jZsgn8Zh0dVEe_JB0

.. figure:: observations-cell-city.png
    :width: 480px
    :height: 480px
    :scale: 50%
    :align: center
    :alt: A cell signal in a city partially covers a block. Most of the
          observations are along roads surrounding that block. The station
          model places the station near the center of the block, with a
          radius that covers the observations, but does not include the
          actual cell signal.

Outside of cities, a cell tower often covers a large area, and individual
cell signals are broadcast in narrow wedges. The observations may be a
large distance away from the emitter, along cross-country roads. The station
model is often centered on these roads, and the cell signal source is well
outside of the radius.

.. Source:
.. https://docs.google.com/drawings/d/1b_BDsdfco9ctXVHvWK7RSGmgOM5ssz-gYauhf564GVc

.. figure:: observations-cell-country.png
    :width: 480px
    :height: 223px
    :scale: 50%
    :align: center
    :alt: A cell signal in the country that is a distance from the tower.
          Most of the observations are along a straight cross-country road.
          The station model is centered on the middle of the road section
          covered by the station.

Sources and Batching
====================

Observations come from two sources:

Location queries
  The device sends the detected radio sources, and Ichnaea returns a position
  estimate or region based on known stations and the requester's IP address.
  This data is used to discover new stations, and to confirm that known
  stations are still active.

Submission reports
  The device sends the detected radio stations, along with a position, which is
  usually derived from high-precision satellite data such as GPS.  These
  reports are used to determine the position of newly discovered stations, or
  to refine the position estimates of known stations.

The :ref:`data flow process <position-data-flow>` creates observations by
pairing the position data with each station, and then adds the observations to
update queues based on the database sharding. Cell stations are split by radio
type, and the observations are added to queues like ``update_cell_gsm`` and
``update_cell_wcdma``.  Bluetooth and WiFi stations are split into 16 groups by
the first hexadecimal letter of the identifier, and the observations are added
to queues like ``update_wifi_0`` and ``update_blue_a``.

These per-shard queues are processed when a large enough batch is accumulated,
or when the queue is about to expire.  Batching increases the chances that
there will be several observations for a station processed in the same chunk.
It also increases the chance that two station updating threads will try to
update the same station. This may cause timeouts or deadlocks due to lock
contention, and is tracked with the metric ``data.station.dberror``.

Observation Weight
==================

Each observation is assigned a weight, to determine how much it should contribute
to the station position estimate, or if it should be discarded completely. The
observation weight is based on four metrics:

Accuracy
  Expected distance from the reported position to the actual position, in
  meters.

Age
  The time from when the radio was seen until the position was recorded, in
  seconds. The age can be negative for observations after the position was
  recorded.

Speed
  The speed of the device when the position was recorded, in meters per second.

Signal
  The strength of the radio signal, in dBm (decibel milliwatts).

The observation weight is the product of four weights:

  **(accuracy weight) x (age weight) x (speed weight) x (signal weight)**

The first three weights range from 0.0 to 1.0. If the accuracy radius is too
large (200m for WiFi), the age is too long ago (20 seconds), or the device is
moving too quickly (50m/s), the weight is 0.0 and the observation is discarded.
If the accuracy distance is small (10m or less), the age is very recent (2s or
less), and the device is moving slowly (5m/s or less), then the weight is 1.0.

The signal weight for cell and WiFi stations is 1.0 for the average signal
strength (-80 dBm for WiFi, -105 dBm to -95 dBm for different cell
generations), grows exponentially for stronger signals, and drops exponentially
for weaker signals. It never reaches 0.0, so signal strength does not
disqualify an observation in the same way as accuracy, age, or speed. For
bluetooth stations, the signal weight is always 1.0.

When accuracy, age, speed, or signal strength is unknown, the weight for that
factor is 1.0.

An observation weight of 0.0 disqualifies that observation. An average
observation should have a weight of 1.0. Weights are used when averaging
observation positions, and when adjusting the position of an existing station.
Existing stations store the sum of weights of previous observations, so that
new observations have a smaller influence on position over time.

For more information, see `Weight Algorithm Details`_.

Blocked Stations
================
Only stationary cell, WiFi, and Bluetooth stations should be considered when
estimating a position for a location query. Mobile stations are identified
by observations that are well outside the expected range of the station type.
Ichnaea keeps track of these as blocked stations, and uses observations to keep
them blocked or move them back to regular stations.

When a station is blocked, it remains blocked for 48 hours. This temporary
block is used to handle a usually stationary station that is moved, such as a
WiFi access point that moves to a new location.

A station's block count is tracked, and compared to how long the station has
been tracked. If a station has been blocked more times than its age in 30-day
"months", then it is considered a mobile station and remains in a long-term
block. For example, if a station tracked for a year has been blocked 12 times
or more, it remains in a long-term block.

Observations for blocked stations are added to the daily observation count, but
are not processed to update the station. Blocked stations do not store a
position estimate, but retain a region if they once had a position estimate,
and can still be used for region queries.

Updating Stations
=================
The observations (with non-zero weights) for a station are processed as a
group, to determine how the station should be updated. If there are valid
GPS-based observations, only those are used, discarding any observations based
on location queries.

If an existing station is still blocked, then it remains blocked. For unblocked
stations, here is the decision process for determining what the "transition
state", or update type, should be:

.. Original at:
.. https://docs.google.com/drawings/d/12oo7ffQWZf5L5_Q0dnN5WBM88PVrT6pYv1V5AmFtUrA

.. image:: observations-flowchart.png
    :width: 796px
    :height: 1050px
    :scale: 75%
    :align: center
    :alt: A flowchart showing how the facts are used to determine what kind of
          update to make the the station.

Several yes-or-no facts are used to determine the update type:

* *Station Exists?* - Is there a record for this station in the database?
* *Consistent Position?* - Are multiple observations close enough that they
  could be observing the same stationary station, or are they spread out enough
  that they could be observing different stations or a moving station? The
  "close enough" radius changes based on the type of station (100m for
  Bluetooth, 5km for WiFi, and 100km for cell stations).
* *Station Has Position?* - Does the station have a position estimate in the
  database?
* *Position Agrees?* - Does the station position agree with the observations,
  or do the observations suggest the station has moved?
* *Old Position?* - Has the station's position not been confirmed for over a
  year?
* *GNSS Station?* - Is the station's position based on Global Navigation
  Satellite System data, such as GPS?
* *GNSS Position?* - Is the observation based on a GNSS position submission,
  rather than a location query?

These are used to determine a transition state:

* *No Change* - No change is made to the station
* *New* - A new station is added to the database.
* *New Block* - A new blocked station is added to the database.
* *Change* - An existing station's position is adjusted, based on the weighted
  average of the current position and the observations.
* *Confirm* - An existing station is confirmed to still be active today.
  Stations that were already confirmed today are unchanged.
* *Replace* - A station's position is replaced with the observation position
* *Block* - A station's position is removed, and it is blocked from being used
  for location queries

Related cell stations are grouped into a *cell area*. These can be used for
location queries, when a particular cell station is unknown but others in the
cell area group are known. If a cell station is created or has an updated
position (all transition states but *No Change* or *Confirm*), then the cell
area is added to a queue `update_cellarea`, and processed when enough cell
areas are accumulated.

Metrics are collected based on the update type. There is a daily count of
observations, and a count of newly tracked stations, both by radio type, stored
in Redis. There are four statsd counters as well:

* ``data.observation.insert`` - Counts all observations with a non-zero weight,
  including those observing a blocked station
* ``data.station.blocklist`` - Counts new stations that start blocked (*New
  Block*) and stations converted to blocked (*Block*)
* ``data.station.confirm`` - Counts existing stations confirmed to still be
  active (*Confirm*)
* ``data.station.new`` - Counts new stations added, either as blocked stations
  (*New Block*), or non-blocked stations (*New*)

Weight Algorithm Details
========================

The observation weight is the product of four weights:

  **(accuracy weight) x (age weight) x (speed weight) x (signal weight)**

The accuracy, age, and speed weights use the same algorithm, with these
features:

* The weight is 1.0 if the metric is small enough (at or below **MIN**), fully
  weighting the observation. If the metric is unknown, the weight is also 1.0.
* The weight is 0.0 if the metric is too large (at or above **MAX**), rejecting
  the observation.
* The weight drops logarithmically from 1.0 if the metric is between **MIN**
  and **MAX**.

.. Original from
.. https://docs.google.com/spreadsheets/d/1C_Ui3t1rl4uRfWktUVzShm3OEnw_ZaYqQeH4oVoRaO8

.. figure:: observations-qualifying-weight.png
    :width: 600px
    :height: 371px
    :align: center
    :alt: A generic chart of the qualifying weight algorithm, as described above.
    :figclass: align-center

    The weight curve for qualifying metrics

+----------+-----------------+------------+-------------+---------------------+
| Metric   | MIN, Weight=1.0 | Weight=0.5 | Weight=0.33 | MAX, Weight=0.0     |
+==========+=================+============+=============+=====================+
| Accuracy |            10 m |       40 m |        90 m | | 100 m (Bluetooth) |
|          |                 |            |             | | 200 m (WiFi)      |
|          |                 |            |             | | 1000 m (Cell)     |
+----------+-----------------+------------+-------------+---------------------+
| Age      |             2 s |        8 s |        18 s | 20 s                |
+----------+-----------------+------------+-------------+---------------------+
| Speed    |           5 m/s |     20 m/s |      45 m/s | 50 m/s              |
+----------+-----------------+------------+-------------+---------------------+

The signal weight algorithm varies by radio type. The signal weight is always
1.0 for Bluetooth. For WiFi and Cell radios, the weight is 1.0 for the average
signal, and grows exponentially as the signal gets stronger.

.. Original from
.. https://docs.google.com/spreadsheets/d/1C_Ui3t1rl4uRfWktUVzShm3OEnw_ZaYqQeH4oVoRaO8

.. figure:: observations-signal-weight.png
    :width: 600px
    :height: 371px
    :align: center
    :alt: A generic chart of the signal weight algorithm, as described above.
    :figclass: align-center

    The weight curve for signal strength

Here are the signal strengths for interesting weights:

+-------+------------+------------------+------------+------------+
| Radio | Weight=0.5 | Weight=1.0 (Avg) | Weight=2.0 | Weight=4.0 |
+=======+============+==================+============+============+
| WiFi  | -98.9 dBm  | -80 dBm          | -64.1 dBm  | -50.7 dBm  |
+-------+------------+------------------+------------+------------+
| GSM   | -113.9 dBm | -95 dBm          | -79.1 dBm  | -65.7 dBm  |
+-------+------------+------------------+------------+------------+
| WCDMA | -118.9 dBm | -100 dBm         | -84.1 dBm  | -70.7 dBm  |
+-------+------------+------------------+------------+------------+
| LTE   | -123.9 dBm | -105 dBm         | -89.1 dBm  | -75.7 dBm  |
+-------+------------+------------------+------------+------------+

If the signal strength is unknown, a signal weight of 1.0 is used.
