=============
Changelog 1.4
=============

1.4 (2016-03-03)
================

20160303094100
**************

Changes
~~~~~~~

- Deprecate hashkey and internaljson logic.

- Improve readability of downloads page.

- Restrict valid characters in API keys.

- Take signal strength into account for location queries.

- Decrease database session times in data tasks.

- Retry station updates on deadlocks and lock timeouts.

- Simplify and speed up InternalUploader.

20160218132400
**************

Changes
~~~~~~~

- Display region specific BLE statistics.

- Remove geodude compatibility API again.

- Avoid intermediate Redis task round-trip.

- Queue data for up to 24 hours.

- Simplify colander schemata.

- Update dependencies.

20160202154300
**************

Changes
~~~~~~~

- Avoid fancy syntax in build requirements.

20160202101600
**************

Migrations
~~~~~~~~~~

- 4b11500c9014: Add Bluetooth region stat.

- b247526b9501: Add sharded Bluetooth tables.

- 0987336d9d63: Add weight and last_seen columns to station tables.

- 44e1b53944ee: Remove old cell tables.

Changes
~~~~~~~

- #476: Emit basic request metrics for region API.

- Remove internal API key human readable metric names.

- Accept and use Bluetooth networks in public HTTP APIs.

- Weight observations by their accuracy and signal strength values.

- Add stricter validation of asu, signal and ta values.

- Restrict observations to maximum accepted accuracy values.

- Allow queries to the fallback source if the combined score is too low.

- #151: Choose best position result based on highest combined score.

- #481: Fix broken cell export.

- #151: Choose best region result based on highest combined score.

- #371: Extend region API to use wifi data.

- #371: Extend region API to use cell area data.

- #151: Choose best region result based on highest score.

- Remove migrations and tests for 1.2 to 1.3 upgrade.

- Enable `shapely.speedups` to speed up GeoJSON parsing.

- Ship buffered region file with the code.

- Stop forwarding client IP address to data pipeline.

20160112143200
**************

Migrations
~~~~~~~~~~

- 9743e7b8a17a: Add allow_locate column to API key table.

- 5d245a440c6f: Remove unused user email field.

- d350610e27e: Shard cell table.

- 40d609897296: Add sharded cell tables.

- The command line for starting gunicorn has changed. The `-c` option now
  needs a `python:` prefix and has to be `-c python:ichnaea.webapp.settings`.

Changes
~~~~~~~

- #478: Restrict some API keys from using the locate API.

- Register OCID import tasks based on the configuration file.

- #471: Remove sentence about Firefox OS.

- #477: Decrease cell maximum radius to 100 km.

- Use sharded cell tables.

- Keep separate rate limits per API version.

- Update to latest versions of dependencies.

20151118134500
**************

Migrations
~~~~~~~~~~

- 91fb41d12c5: Drop mapstat table.

Changes
~~~~~~~

- #469: Update to static tabzilla.

- #468: Add CORS headers and support OPTIONS requests.

- #467: Implement geodude compatibility API.

- #151: Choose best WiFi cluster based on a data quality score.

- Use up to top 10 WiFi networks in WiFi location.

- Use proper agglomerative clustering in WiFi clustering.

- Remove arithmetic/hamming distance analysis of BSSIDs.

- Accept and forward WiFi SSID's in public HTTP API's.

20151105120300
**************

Migrations
~~~~~~~~~~

- 78e6322b4d9: Copy mapstat data to sharded datamap tables.

- 4e8635b0f4cf: Add sharded datamap tables.

Changes
~~~~~~~

- Use new sharded datamap tables.

- Parallelize datamap CSV export, Quadtree generation and upload.

- Introduce upper bound for cell based accuracy numbers.

- Fix database lookup fallback in API key check.

- Switch randomness generator for data map, highlight more recent additions.

- Update to latest versions of lots of dependencies.

20151021143400
**************

Migrations
~~~~~~~~~~

- 450f02b5e1ca: Update cell_area regions.

- 582ef9419c6a: Add region stat table.

- 238aca86fe8d: Change cell_area primary key.

- 3fd11bfaca02: Drop api_key log column.

- 583a68296584: Drop old OCID cell/area tables.

- 2c709f81a660: Rename cell/area columns to radius/samples.

Changes
~~~~~~~

- Maintain `block_first` column.

- Introduce upper bound for Wifi based accuracy numbers.

- Provide better GeoIP accuracy numbers for cities and subdivisions.

- Fix cell queries containing invalid area codes but valid cids.

- #242: Add WiFi stats to region specific stats page.

- Add update_statregion task to maintain region_stat table.

- Update to latest versions of alembic, coverage, datadog, raven
  and requests.

20151013115000
**************

Migrations
~~~~~~~~~~

- 33d0f7fb4da0: Add api_type specific logging flags to api keys.

- 460ce3d4fe09: Rename columns to region.

- 339d19da63ee: Add new cell OCID tables.

- All OCID data has to be manually imported again into the new tables.

Changes
~~~~~~~

- Add new `fallback_allowed` tag to locate metrics.

- Calculate region radii based on precise shapefiles.

- Use subunits dataset to preserve smaller regions.

- Use GENC codes and names in GeoIP results.

- Consider more responses as high accuracy.

- Change internal names to refer to region.

- Change metric tag to region for region codes.

- Temporarily stop using cell/area range in locate logic.

- Discard too large cell networks during import.

- Use mcc in region determination for cells.

- Use new OCID tables in the entire code base.

- Use the intersection of region codes from GENC and our shapefile.

- Avoid base64/json overhead for simple queues containing byte values.

- Maintain a queue TTL value and process remaining data for inactive queues.

- Remove hashkey functionality from cell area models.

- Remove non-sharded update_wifi queue.

- Merge scan_areas/update_area tasks into a single new update_cellarea task.

- Remove backwards compatible tasks and area/mapstat task processing logic.

- Update to latest versions of bower, clean-css and uglify-js.

- Update to latest versions of cryptography, Cython, kombu, numpy,
  pyasn1, PyMySQL, requests, Shapely, six and WebOb.

20150928100200
**************

Migrations
~~~~~~~~~~

- 26c4b3a7bc51: Add new datamap table.

- 47ed7a40413b: Add cell area id columns.

Changes
~~~~~~~

- Improve locate accuracy by taking station circle radius into account.

- Split out OCID cell area updates to their own queue.

- Switch mapstat queue to compact binary queue values.

- Speed up update_area task by only loading required cell columns.

- Validate all incoming reports against the region areas.

- Add a precision reverse geocoder for region lookups.

- Add a finer grained region border file in GeoJSON format.

- Shard update_wifi queue/task by the underlying table shard id.

- Update datatables JS library and fix default column ordering.

- Switch to GENC dataset for region names.

- #372: Add geocoding / search control to map.

- Support the new `considerIp` field in the geolocate API.

- #389: Treat accuracy, altitude and altitudeAccuracy as floats.

- Speed up `/stats/regions` by using cell area table.

- Use cell area ids in update_cellarea task queue.

- Enable country level result metrics.

- Removed migrations before version 1.2.

- Update to latest versions of numpy, pytz, raven, rtree and Shapely.
