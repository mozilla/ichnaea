=========
Changelog
=========

1.5 (unreleased)
================

Untagged
********

Migrations
~~~~~~~~~~

- 6ec824122610: Add export config table.

- 4255b858a37e: Remove user/score tables.

Changes
~~~~~~~

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
