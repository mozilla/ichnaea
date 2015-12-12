=============
Changelog 1.3
=============

1.3 (2015-09-16)
================

20150916130500
**************

Migrations
~~~~~~~~~~

- b24dbb9ccfe: Remove CDMA networks.

- 18d72822fe20: Remove wifi table.

Changes
~~~~~~~

- Stop importing and exporting CDMA networks.

- #222: Maintain a country/region code estimate for new wifi networks.

- Add new `location_load` script to load cell dumps into a local db.

- Remove obsolete `remove_wifi` task.

- Update to latest versions of certifi, cryptography, coverage and Cython.

20150903095100
**************

Migrations
~~~~~~~~~~

- Manually run the wifi migration script in `scripts/migrate.py`.

Changes
~~~~~~~

- Stop using the wifi table.

- Update to latest versions of datadog, greenlet, mako and raven.

20150828125400
**************

Changes
~~~~~~~

- Fix bug in block_count station update routine.

20150827110300
**************

Migrations
~~~~~~~~~~

- c1efc747c9: Remove unused api_key email/description columns.

- 4f12bf0c0828: Remove standalone wifi blocklist table.

Changes
~~~~~~~

- Insert new wifi networks into sharded tables.

- Factor out more of the `aggregate position` logic.

- Optimize gzip compression levels.

- Add new celery queues (`celery_cell`, `celery_ocid`, `celery_wifi`).

- Remove extra internal_dumps call from insert task.

- Add a source tag for successful result metrics.

- Update data tables and stats/regions page.

- Setup Cython support and convert geocalc centroid and distance functions.

- Optimize OCID cell data export and import.

- Return multiple results from MCC based country source.

- Move best country result selection into searcher logic.

- Update to latest versions of alembic, cffi, cryptography, coverage,
  cython, hiredis, numpy, pip and scipy.

20150813105600
**************

Changes
~~~~~~~

- Use data_accuracy as the criteria to decide if more locate sources
  should be consulted.

- Use both old and new wifi tables in locate logic.

- Add a new `__version__` route.

- Cache Wifi-only based fallback position results.

- Don't rate limit cache lookups for the fallback position source.

- Retry outbound connections once to counter expired keep alive connections.

20150806105100
**************

Migrations
~~~~~~~~~~

- 2127f9dd0ed7: Move wifi blocklist entries into wifi shard tables.

- 4860cb8e54f5: Add new sharded wifi tables.

- The structure of the application ini file changed and the `ichnaea`
  section was replaced by a number of new more specific sections.

Changes
~~~~~~~

- Enable SSL verification for outbound network requests.

- Add new metrics for counting unique IPs per API endpoint / API key.

- Enable locate source level metrics.

- #457: Fix cell export to again use UMTS as the radio type string.

- Optimize various tasks by doing batch queries and inserts.

- Avoid using a metric tag called `name` as it conflicts with a default tag.

- Deprecate `insert_measure_*` tasks.

- Move new station score bookkeeping into insert_measures task.

- Update to latest version of datadog.

20150730143600
**************

Changes
~~~~~~~

- Make report and observation drop metrics more consistent.

20150730111000
**************

Migrations
~~~~~~~~~~

- The statsd configuration moved from the `statsd_host` option in the
  application ini file into its own section called `statsd`.

Changes
~~~~~~~

- Move blocklist and station creation logic into update_station tasks.

- Add new `ratelimit_interval` option to `locate:fallback` section.

- Set up a HTTPS connection pool used by the fallback source.

- Disable statsd request metrics for static assets.

- Let all internal data pipeline metrics use tags.

- Let all public API and fallback source metrics use tags.

- Let task, datamaps, monitor and HTTP counter/timer metrics use tags.

- Add support for statsd metric tagging.

- Use colander to map external to internal names in submit schemata.

- Add dependencies pyopenssl, ndg-httpsclient and pyasn1.

- Switch to datadog statsd client library.

- Consider Wifi based query results accurate enough to satisfy queries.

- Stop maintaining separate Python dependency list in setup.py.

- #433: Move GeoIP lookup onto the query object.

- #433: Add new detailed query metrics.

- Use a colander schema to describe the outbound fallback provider query.

- Set up and configure locate searchers and providers once during startup.

- Move all per-query state onto the locate query instance.

- Split customjson into internal and external pretty float version.

- Update to latest versions of alembic, setproctitle, simplejson and
  SQLAlchemy.
