=========
Changelog
=========

1.5 (unreleased)
================

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
