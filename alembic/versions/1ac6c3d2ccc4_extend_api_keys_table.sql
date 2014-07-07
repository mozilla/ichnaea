-- Running upgrade 23a8a4ccc96f -> 1ac6c3d2ccc4

ALTER TABLE api_key ADD COLUMN shortname VARCHAR(40);

ALTER TABLE api_key ADD COLUMN email VARCHAR(255);

ALTER TABLE api_key ADD COLUMN description VARCHAR(255);

UPDATE alembic_version SET version_num='1ac6c3d2ccc4';
