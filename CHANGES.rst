=========
Changelog
=========

1.5 (unreleased)
================

Untagged
********

Migrations
~~~~~~~~~~

- fdd0b256cecc: Add fallback options to API key table.

Changes
~~~~~~~

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
