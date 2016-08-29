=============
Changelog 1.5
=============

1.5 (unreleased)
================

Untagged
********

Migrations
~~~~~~~~~~

Changes
~~~~~~~

- Add a workaround for a bug in the RTree library.

20160810110400
**************

Migrations
~~~~~~~~~~

- 385f842b2526: Add allow_transfer column to api_key table.

Changes
~~~~~~~

- Use a docker volume for the css/js build pipeline.

20160809152200
**************

Changes
~~~~~~~

- Add a new `location_dump` command line script to dump/export networks.

- #491: Add an alternate homepage if the web content is disabled.

- Reduce datamap detail.

- No longer log sentry messages for client errors.

- Replace station data for old stations with new conflicting observations.

- Make statsd and sentry optional service dependencies.

- Disable the web site content by default.

- #490: Limit full cell export to cells which were modified in the last year.

- Use the accuracy_radius field from the GeoIP database.

- Remove ipf fallback from responses for queries based only on GeoIP data.

20160525130100
**************

Migrations
~~~~~~~~~~

- Remove the celery section from the config file, add the web section.

Changes
~~~~~~~

- Lower maximum accuracy values returned from locate queries.

- Accept observations with slightly worse accuracy values.

- The website content can be disabled via a setting in the config file.

- Make map related settings configurable via the config file.

- Use the first of the month, to display stats for the entire month.

- Calculate and display stats for today.

- Preserve or derive both WiFi channel and frequency values.

20160429092200
**************

Changes
~~~~~~~

- Allow report submissions without any position data.

- #485: Fix development documentation.

20160427100000
**************

Migrations
~~~~~~~~~~

- 1bdf1028a085: Extend export config table.

- 6ec824122610: Add export config table.

- 4255b858a37e: Remove user/score tables.

- In service checks, change anything that checked the `/__heartbeat__`
  view to check `/__lbheartbeat__` instead. Change `/__monitor__` to
  `/__heartbeat__`.

Changes
~~~~~~~

- Be more explicit about closing socket connections.

- Use GNSS observations to replace purely query-based stations.

- Use query observations to confirm, blocklist and insert new stations.

- Configure release for raven/sentry client.

- Change hearbeat/monitor view to lbhearbeat/hearbeat views.

- Update last_seen column on each station update.

- Use Vincenty formula for lat/lon additions.

- Use Vincenty instead of Haversine formula for distance calculations.

- Take age into account during locate lookups.

- Filter out observations with too little weight.

- Take age and speed into account in observation weights.

- Pass queries into internal data pipeline.

- Allow stations to be blocklisted once per 30 days of their lifespan.

- Normalize age fields for internal observations to GPS time difference.

- Add stricter validation of radio, source and timestamp fields.

- Pass pressure and source data into internal data pipeline.

- Read export config from database instead of ini file.

20160412083700
**************

Migrations
~~~~~~~~~~

- 27400b0c8b42: Drop api_key log columns.

- 88d1704f1aef: Drop cell_ocid table.

Changes
~~~~~~~

- Remove intermediate schedule_export_reports task.

- #456: Retire old leaderboard.

- Remove intermediate upload_report task.

20160401185900
**************

Changes
~~~~~~~

- Downgrade numpy to 1.10.4 due to build failures.

20160401110200
**************

Migrations
~~~~~~~~~~

- e23ba53ab89b: Add sharded OCID cell tables.

- fdd0b256cecc: Add fallback options to API key table.

Changes
~~~~~~~

- Tag location fallback metrics with the fallback name.

- #484: Allow per API key fallback configuration.

- Document and forward age argument through all layers of abstraction.

- Limit the columns loaded for API keys.

- Prevent errors when receiving invalid timestamps.

20160323102800
**************

Changes
~~~~~~~

- #456: Deprecate weekly leaderboard.

- Remove the implied metadata setting from the config file.

- Enable extended metrics for all API keys.

- Speed up full cell export.

- Rename internal blue/wifi observation key to mac.

- Removed migrations before version 1.4.
