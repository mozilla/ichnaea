=============
Changelog 1.2
=============

1.2 (2015-07-15)
================

20150716174000
**************

Changes
~~~~~~~

- Add a database migration test from a fresh SQL structure dump.

Migrations
~~~~~~~~~~

- 1a320a751cf: Remove observation tables.

Changes
~~~~~~~

- #395: Move `incomplete_observation` logic onto colander schema.

- #287: Replace observation models with non-db-model classes.

- #433: Move query data validation into Query class.

- #433: Introduce a new `api.locate.query.Query` class.

- Handle any RedisError, e.g. TimeoutError and not just ConnectionErrors.

- Update to latest raven release and update transport configuration.

- Explicitly limit the cell cache key to its unique id parts.

- Add `fallback` key to all locate responses.

- #451: Properly test and reject empty submit requests.

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

- Update to latest versions of all CSS and JS dependencies.

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
