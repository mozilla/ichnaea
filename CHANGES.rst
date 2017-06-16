=========
Changelog
=========

2.1.0 (unreleased)
==================

Compatibility
~~~~~~~~~~~~~

- Drop support for Python 2.7, require Python 3.6.

Migrations
~~~~~~~~~~

Changes
~~~~~~~

- Replace bower in CSS/JS dev setup with npm.

- Install MySQL 5.7 and Redis command line utilities.

- Remove radio field workaround in cell locate API.

- Adjust the text on the download and stats pages.

- Use SQLAlchemy core instead of ORM in various places.


2.0 (2017-03-22)
================

Compatibility
~~~~~~~~~~~~~

- Application configuration moved to environment variables.

- Moved initial database schema creation into an alembic migration.

- Test against Redis 3.2 instead of 2.8.

- Test against MySQL 5.7 instead of 5.6.

- No longer create `lbcheck` database user in `location_initdb` script.

- Drop support for Python 2.6.

Migrations
~~~~~~~~~~

- d2d9ecb12edc: Add modified index on `datamap_*` tables.

- cad2875fd8cb: Add `store_sample_*` columns to api_key table.

- Removed old migrations. The database needs to be at least at version
  `1bdf1028a085` or `385f842b2526` before upgrading to this version.

Changes
~~~~~~~

- #496: Don't store queries if all networks where seen today.

- #492: Add new datamap cleanup task to delete old datamap rows.

- Update to botocore/boto3.

- No longer use secondary cell tables during lookups.

- Remove continous cell import functionality.

- Relax GeoIP database check to allow `GeoLite2-City` databases.

- Update region specific statistics once per day.

- Add in-memory API key cache.

- Add `/contribute.json` view.

- Update to Celery 4.

- Remove `/leaders` HTTP redirects.

- Replace the `/apps` page with a link to the Wiki.
