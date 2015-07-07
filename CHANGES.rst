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

- #376: Document the added home mcc/mnc fields.

- #419: Update geolocate docs to mention all GLS fields.

20150707130400
**************

Migrations
~~~~~~~~~~

- 2e0e620ebc92: Remove id column from content models.

Changes
~~~~~~~

- Add workaround for andymccurdy/redis-py#633.

- Unify v1 and v2 parse error responses to v2 format.

- Batch key queries depending on a per-model batch size.

- #192: Suggest a observation data retention period.

- Optimize mapstat and station data tasks.

- Switch to using bower for CSS/JS dependency management.

- Updated to latest versions of all CSS and JS dependencies.

- Update to latest versions of geoip2, SQLAlchemy and unittest2.

20150616104200
**************

Migrations
~~~~~~~~~~

- 55db289fa497: Add content model composite primary keys.

- 14dbafc4fec2: Remove new_measures indices.

- 19d6d9fbdb6b: Increase stat table value column to biginteger.

Changes
~~~~~~~

- Fix locate errors for incomplete cell keys.

- Remove backwards compatibility code.

20150610103900
**************

Migrations
~~~~~~~~~~

- 38fde2949750: Remove measure_block table.

Changes
~~~~~~~

- #287: Remove table based location_update tasks and old backup code.

- Adjust batch sizes for new update_station tasks.

- Bugzilla 1172833: Use apolitical names on country stats page.

- #443: Reorganize internal module/classes.

- Update to latest version of SQLAlchemy.

20150604164500
**************

Changes
~~~~~~~

- #446: Filter out incomplete csv cell records.

- #287: Switch location_update tasks to new queue based system.

- #438: Add explicit fallback choices to geolocate API.

- Replace the last daily stats task with a queue based one.

- #440: Allow search/locate queries without a cell id.

- Update to latest versions of nose, simplejson and SQLAlchemy.

20150528085200
**************

Changes
~~~~~~~

- #394: Replace magic schema values by `None`.

- #423: Add new public `v2/geosubmit` API.

- #242: Pass through submission IP address into the data pipeline.

- #242: Expose geoip database to async tasks.

- Make sure there are no unexpected raven messages left after each test.

- #434: Internal test only changes to test base classes.

- Update to latest versions of gevent and simplejson.

20150522094900
**************

Changes
~~~~~~~

- #421: Pass through additional lookup data into the fallback query.

- #421: Cache cell-only lookups for fallback provider queries.

- #421: Add rate limiting to fallback provider.

- #421: Reordered data sources to prefer fallback over geoip responses.

- Fix api-key specific report upload counter.

- Add workaround for raven issue #608.

- Enable new stat counter tasks.

- #433: Remove the wifi specific query stats.

- Updated to latest version of alembic, celery, greenlet, kombu and pytz.

20150507103300
**************

Changes
~~~~~~~

- Correct handling for requests without API keys.

- #421: Fix encoding of radioType in fallback queries.

20150505113200
**************

Migrations
~~~~~~~~~~

- e9c1224f6bb: Add allow_fallback column to api_key table.

Changes
~~~~~~~

- #287: Move mapstat and score processing to separate queues/tasks.

- #287: Keep track of uploaded data via Redis stat counters.

- #287: Add new backup to S3 export target.

- #421: Add fallback geolocation provider.

- Deal with nan/inf floating point numbers in data submissions.

- Fixed upload issues for cell entries without any radio field.

- Updated to latest versions of certifi, greenlet, pyramid, raven and requests.

20150423105800
**************

Changes
~~~~~~~

- Allow anonymous data submission via the geosubmit API.

- #425: Refactor internal API key logic.

- Updated to latest raven version, requires a Sentry 7 server.

- Updated to latests versions of billiard, pyramid and WebOb.

20150416111700
**************

Migrations
~~~~~~~~~~

- The command line invocation for the services changed, please refer to
  the deploy docs for the new syntax.

Changes
~~~~~~~

- #423: Add a first version of an export job.

- Expose all config file settings to the runtime services.

- Move runtime related code into async/webapp sub-packages.

- #385: Configure Python's logging module.

- #423: Add a new queue system using the new geosubmit v2 internal format.

- Updated to latest versions of boto and maxminddb.

20150409120500
**************

Changes
~~~~~~~

- Make radio an internally required field.

- Don't validate radio fields in request side schema.

- #418: Remove country API shortcut implementation.

- Removed BBB code for old tasks and pre-hashkey queued values.

- Updated to latest versions of alabaster, boto, factory_boy and pytz.

20150320100800
**************

Changes
~~~~~~~

- Remove the circus docs and example ini file.

- Remove the vaurien/integration tests.

- #416: Accept radioType inside the cellTowers mapping in geolocate queries.

- Updated to latest version of Sphinx and its new dependencies.

- Updated to latest versions of pyramid, requests, SQLAlchemy and statsd.

20150309175500
**************

- Fix unittest2 version pin.

20150305122500
**************

Migrations
~~~~~~~~~~

- 1d549c1d6cfe: Drop total_measures index on station tables.

- 230bbf3fe044: Add index on mapstat.time column.

- 6527bee5ac1: Remove auto-inc id columns from cell related tables.

- 3b8d52a9eac4: Change score, stat and measure_block enum columns to tinyint.

Changes
~~~~~~~

- Replace heka-py-raven with a direct raven client.

- #319: Remove the per station ingress filtering.

- Allow partial cell ids in geolocate/geosubmit APIs.

- Removed the mixed locate/submit mode from the geosubmit API.

- #402: Avoid multiple validation of common report data fields.

- Add a new CellCountryProvider to allow country searches based on cell data.

- #406: Allow access to the country API via empty GET requests.

- Massive internal code refactoring and cleanup.

- Updated to latest versions of iso3166, pyramid and requests.

20150211113000
**************

Changes
~~~~~~~

- Reestablish database connections on connection failures.

20150209110000
**************

Changes
~~~~~~~

- Backup/delete all observation data except for the current day.

- Updated to latest versions of boto, Chameleon, gunicorn, jaraco.util, Mako,
  psutil, Pygments, pyzmq and WebTest.

20150203093000
**************

Changes
~~~~~~~

- Specify statsd prefix in application code instead of heka config.

- Fix geoip country lookup for entries without countries.

- #274: Extend monitor view to include geoip db status.

20150127130000
**************

Migrations
~~~~~~~~~~

- 10542c592089: Remove invalid lac values.

- fe2cfea89f5: Change cell/_blacklist tables primary keys.

Changes
~~~~~~~

- #367: Tighten lac filtering to exclude 65534 (gsm) and 65535 (all).

- Remove alembic migrations before the 1.0 PyPi release.

- #353: Remove auto-inc id column from cell/_blacklist tables.

- Add additional stats to judge quality of WiFi based queries.

- #390: Remove command line importer script.

20150122140000
**************

Migrations
~~~~~~~~~~

- 188e749e51ec: Change lac/cid columns to signed integers.

Changes
~~~~~~~

- #352: Switch to new maxmind v2 database format and libraries.

- #274: Add a new `__monitor__` endpoint.

- #291: Allow 32bit UMTS cell ids, tighten checks for CDMA and LTE.

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
