=========
Changelog
=========

2.0 (unreleased)
================

Untagged
********

Compatibility
~~~~~~~~~~~~~

- No longer create `lbcheck` database user in `location_initdb` script.

- Drop support for Python 2.6.

Migrations
~~~~~~~~~~

- cad2875fd8cb: Add `store_sample_*` columns to api_key table.

- Removed old migrations. The database needs to be at least at version
  `1bdf1028a085` or `385f842b2526` before upgrading to this version.

Changes
~~~~~~~

- Add `/contribute.json` view.

- Update to Celery 4.

- Remove `/leaders` HTTP redirects.

- Replace the `/apps` page with a link to the Wiki.
