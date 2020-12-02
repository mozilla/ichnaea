.. _rate_control:

====================================
Processing Backlogs and Rate Control
====================================

Ideally, all :term:`observations` would be used to update the Ichnaea database.
However, this can quickly become impractical. The backend resources, such as
worker servers, the cache, and the database, need to be capable of handling the
peak traffic, when the most observations are generated.  The traffic is
probably not steady, but instead cyclical, which means the backlog resources
are over-provisioned at most times. There is a complex relationship between
API traffic and observations, making it difficult to determine the correct
backend resources.

.. Source document:
.. https://docs.google.com/spreadsheets/d/13L6RTfr-ttevGJYRrhxFkIJtssr2I4sKgRYYlJU3MFE/edit?usp=sharing

.. figure:: images/monthly_traffic.svg
   :width: 700px
   :height: 430px
   :align: center
   :alt: Monthly traffic to service. There is a daily cycle as well as a weekly cycle, and the trend is up.

When the backend is unable to process observations, a backlog builds up. This
is acceptable for traffic spikes, and the backend works through the backlog
when the traffic returns to normal.

When traffic consistently exceeds the capacity of the backend, a steadily
increasing backlog is generated, causing problems.  A large backlog tends to
slow down the cache and database, which can contribute to the backlog
continuing to increase. The backlog is stored in Redis, which eventually runs
out of memory. At that point, Redis really slows down as it determines what
data it can throw away, resulting in slow API requests and timeouts.
Eventually, Redis will discard entire backlogs, "fixing" the problem but losing
data.  An administrator can monitor the backlog by looking at Redis memory
usage and at the :ref:`queue Metric <queue-metric>`.

The chart below shows what a steadily increasing backlog looks like. The
backlog would take less than an hour to clear, but new observations continue to
be added from API usage.  Around 3 PM, API usage generates fewer observations,
allowing the backend to make progress on reducing the backlog. Around 6 PM,
after an hour of lower traffic, the API usage exceeds the backend capabilities
again, and the backlog begins increasing.

.. Source document:
.. https://docs.google.com/spreadsheets/d/1FQMB6tof7atdrWY_hqwL5t-PBjVklktjF56u8ZJ1lZw/edit?usp=sharing

.. figure:: images/backlog_due_to_excess_observations.svg
   :width: 700px
   :height: 430px
   :align: center
   :alt: A backlog builds up from 6 AM to 3 PM, takes nearly 3 hours to clear, and starts building again.

If API usage increases, the backend will be unable to recover in a full 24 hour
cycle, leading to slower service and eventually data loss.

Ichnaea has rate controls that can be used to sample incoming data, and reduce
the observations that need to be processed by the backend.

Rate Control by API Key
=======================
There are two rate controls that are applied by API key, in the `api_key`
database table:

* ``store_sample_locate`` (0 - 100) - The percent of locate API calls that are
  turned into observations.
* ``store_sample_submit`` (0 - 100) - The percent of submission API calls that
  are turned into observations

An administrator can use these to limit the observations from large API users,
or to ignore traffic from questionable API users. The default is 100% for new
keys.

Global Rate Control
===================
The Redis key ``global_locate_sample_rate`` is a number (stored as a string)
between 0 and 100.0 that controls a sample rate for all locate calls. This is
applied as a multiple on any API key controls, so if an API has
``store_sample_locate`` set to 60, and ``global_locate_sample_rate`` is 50.0,
the effective sample rate for that API key is 30%.

An administrator can use this control to globally limit observations from
geolocate calls. A temporary rate of 0% is an effective way to allow the
backend to process a large backlog of observations. If unset, the default
global rate is 100%.

There is no global control for submissions.
