Changelog
=========

1.2 (unreleased)
----------------

Untagged
********

Migrations
~~~~~~~~~~


Changes
~~~~~~~

- #274: Add a new `__monitor__` endpoint.

- #311: On station creation optionally use previous blacklist time.

- #378: Use colander for internal data validation.

- Remove explicit queue declaration from celery base task.

- Updated to latest versions of alembic, boto, Chameleon, jaraco.util,
  mobile-codes, psutil, requests-mock, WSGIProxy2 and zope.deprecation.

20150105140000
**************

Migrations
~~~~~~~~~~

- 48ab8d41fb83: Move cell areas into separate table.

Changes
~~~~~~~

- Prevent non-countries from being returned by the country API.

- #368: Add per API key metrics for uploaded batches, reports and observations.

- Clarify metric names related to batches/reports/observations,
  add new `items.uploaded.batch_size` pseudo-timer and
  `items.uploaded.reports` counter.

- Introduce new internal `GeoIPWrapper.country_lookup` API.

- #343: Fall back to GeoIP for incomplete search requests.

- #349/#350: Move cell areas into new table.

- Give all celery queues a prefix to better distinguish them in Redis.

- #354: Remove scan_lacs fallback code looking at new_measures.

- Updated to latest versions of alembic, argparse, billiard, celery, colander,
  filechunkio, iso8601, kombu, PyMySQL, pytz, requests, six,
  WebTest and zope.interface.

20141218093500
**************

- #371: Add new country API.

20141120130000
**************

- Add api key specific stats to count best data lookup hits/misses.

- Validate WiFi data in location lookups earlier in the process.

- #312: Add email field to User model.

- #287: Move lac update scheduling to Redis based queue.

- #304: Auto-correct radio field of GSM cells with large cid values.

- Move responsibility for lac entry deletion into update_lac task.

- Accept more ASU values but tighten signal strength validation.

- #305: Stricter range check for mnc values for non-CDMA networks.

- Add a convenience `session.on_post_commit` helper method.

- #17: Remove the unused code for cell backfill.

- #41: Explicitly allow anonymous data submissions.

- #335: Omit incomplete cell records from exports.

- Delete measures in batches of 10k rows in backup tasks.

- Re-arrange backup tasks to avoid holding db session open for too long.

- Report errors for malformed data in submit call to sentry.

- Report errors during backup job to sentry.

- #332: Fix session handling in map tiles generation.

- Updated to latest versions of argparse, Chameleon, irc, Pygments, pyramid,
  translationstring and unittest2.

20141103125500
**************

- #330: Expand api keys and download sections.

- Close database session early in map tiles generation.

- Close database session early in export task to avoid timeout errors
  while uploading data to S3.

- Optimize cell export task and avoid datetime/unixtime conversions.

- Add an index on cell.modified to speed up cell export task.

- Updated to latest versions of boto, irc, pygeoip, pytz, pyzmq,
  simplejson and unittest2.

20141030113700
**************

- Add play store link for Mozilla Stumbler to apps page.

- Updated privacy notice style to match general Mozilla style.

- Switch gunicorn to use a gevent-based worker.

- Clean last database result from connections on pool checkin.

- Close the database connections even if exceptions occurred.

1.1 (2014-10-27)
----------------

20141027122000
**************

- Lower DB pool and overflow sizes.

- Update Mozilla Stumbler screenshot.

- Update to new privacy policy covering both Fennec and Mozilla Stumbler.

20141023094000
**************

- Updated Fennec link to point to Aurora channel.

- Renamed MozStumbler to Mozilla Stumbler, added new screenshot.

- Increase batch size for `insert_measures_wifi` task.

- Extend queue maximum lifetime for incoming reports to six hours.

- Extend observation task batching logic to apply to cell observations.

- #328: Let gunicorn start without a valid geoip database file.

- Extend the `make release` step to deal with Python files with
  incompatible syntax.

- Update to latest versions of configparser, greenlet, irc and pyzmq.

20141016123300
**************

- Log gunicorn errors to stderr.

- #327: Add an anchor to the leaderboard table.

- Move the measure tables gauges to an hourly task.

- Fix initdb script to explicitly import all models.

20141014161400
**************

- #311: Filter out location areas from unique cell statistics.

- Introduce a 10 point minimum threshold to the leaderboard.

- Change download page to list files with kilobytes (kB) sizes.

- #326: Quantize data maps image tiles via pngquant.

- Optimize file size of static image assets.

- Remove task modules retained for backwards compatibility.

- Update to latest version of SQLAlchemy.

20141009121300
**************

- Add a task to monitor the last import time of OCID cells.

- Change api_key rate limitation monitoring task to use shortnames.

- Small improvements to the manual importer script.

- #276: Fix bug in batch processing, when receiving more than 100
  observations in one submission.

- Refactor some internals and move code around.

- Create a new `lbcheck` MySQL user in the `location_initdb` command.

- Fix `monitor_api_key_limits` task to work without api limit entries.

- #301: Schedule hourly differential imports of OCID cell data.

- Update to latest versions of boto, celery, iso3166, jaraco.util,
  requests and simplejson.

20141002103900
**************

- #301: Add OCID cell data to statistics page.

- Allow a radio type of `lte` for the geolocate API. Relates to
  https://bugzilla.mozilla.org/show_bug.cgi?id=1010284.

- #315: Add a `show my location` control to the map.

- Reverse ordering of download files to display latest files first.

- Extend db ping to retry connections for `2003 connection refused` errors.

- Ignore more exception types in API key check, to continue degraded service
  in case of database downtimes.

- Switch from d3.js/rickshaw to flot.js and prepare graphs to plot multiple
  lines in one graph.

- Make country statistics table sortable.

- Remove auto-increment column from ocid_cell table and make the
  radio, mcc, mnc, lac, cid combination the primary key. Also optimize the
  column types of the lac and cid fields.

- Update to latest versions of alembic, amqp, celery, configparser, cornice,
  greenlet, jaraco.util, kombu, protobuf, psutil, pytz, requests, six,
  Sphinx and WebTest.

- #301: Add code to do continuous updates of the OpenCellID data and add
  license note for OCID data.

20140904094000
**************

- #308: Fixed header row in cell export files.

20140901114000
**************

- #283: Add manual logic to trigger OpenCellID imports.

- Add Redis based caching for SQL queries used in the website.

- #295: Add a downloads section to the website and enable cell export tasks.

- Clarify api usage policy.

- Monitor api key rate limits and graph them in graphite.

- Update to latest versions of nose and simplejson.

- #282: Add a header row to the exported CSV files.

20140821114200
**************

- #296: Trust WiFi positions over GeoIP results.

- Optimized SQL types of mnc, psc, radio and ta columns in cell tables.

- Update to latest versions of country-bounding-boxes, gunicorn and redis.

- #282: Added code to do exports of cell data, both daily snapshots as
  well as hourly diffs. Currently the automatic schedule is still disabled.
  This also adds a new modified column to the cell and wifi tables.

20140812120000
**************

- Include links to blog and new @MozGeo twitter account.

- Update to latest version of alembic, boto, redis, simplejson and statsd.

- Add a monitoring task to record Redis queue length.

- Make a Redis client available in Celery tasks.

- #285: Update favicon, add touch icon and tile image.

- Only retain two days of observation data inside the DB.

- Fixed image tiles generation to generate up to zoom level 13 again.

- #279: Offer degraded service if Redis is unavailable.

- #72: Always log sentry messages for exceptions inside tasks.

- #53: Document testing approaches.

- #130: Add a test for syntactic correctness of the beat schedule.

- #27: Require sufficiently different BSSIDs in WiFi lookups.
  This reduces the chance of being able to look up a single device with
  multiple logical networks.

20140730133000
**************

- Avoid using `on_duplicate` for common update tasks of tables.

- Remove GeoIP country submission filter, as GeoIP has shown to be too
  inaccurate.

- #280: Relax the GeoIP country restriction and also trust the mcc derived
  country codes.

- #269: Improve search logic when dealing with multiple location areas.

- Correctly deal with multiple country codes per mcc value and don't
  restrict lookups to one arbitrary of those countries.

- Fix requirement in WiFi lookups to really only require two networks.

- Added basic setup for documenting internal code API's and use the geocalc
  and service.locate modules as first examples.

- Initialize the application and outbound connections as part of the
  gunicorn worker startup process, instead of waiting for the first
  request and slowing it down.

- Switch pygeoip module to use memory caching, to prevent errors from
  changing the datafile from underneath the running process.

- Introduce 10% jitter into gunicorn's max_requests setting, to prevent
  all worker processes from being recycled at once.

- Update gunicorn to 19.1.0 and use the new support for config settings
  based on a Python module. The gunicorn invocation needs to include
  `-c ichnaea.gunicorn_config` now and can drop various of the other
  arguments.

- Updated production Python dependencies to latest versions.

- Updated supporting Python libraries to latest versions.

- Update clean-css to 2.2.9 and uglify-js to 2.4.15.

- Update d3.js to 3.4.11 and jQuery 1.11.1.

- Changed graphs on the stats page to show a monthly count for the past
  year, closes https://bugzilla.mozilla.org/show_bug.cgi?id=1043386.

- Update rickshaw.js to 1.5.0 and tweak stats page layout.

- Add MLS logo and use higher resolution images where available.

- Always load cdn.mozilla.net resources over https.

- Updated deployment docs to more clearly mention the Redis dependency
  and clean up Heka / logging related docs.

- Split out circus and its dependencies into a separate requirements file.

- Remove non-local debug logging from map tiles generation script.

- Test all additional fields in geosubmit API and correctly retain new
  `signalToNoiseRatio` field for WiFi observations.

- Improve geosubmit API docs and make them independent of the submit docs.

- Update and tweak metrics docs.

- Adjust Fennec link to point to Fennec Nightly install instructions.
  https://bugzilla.mozilla.org/show_bug.cgi?id=1039787

20140715114000
**************

- Adjust beat schedule to update more rows during each location update task.

- Let the backup tasks retain three full days of measures in the DB.

- Remove the database connectivity test from the heartbeat view.


1.0 (2014-07-14)
----------------

- Initial production release.

0.1 (2013-11-22)
----------------

- Initial prototype.
