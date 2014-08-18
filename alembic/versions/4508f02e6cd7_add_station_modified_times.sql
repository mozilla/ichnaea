-- Running upgrade 2f26a4df27af -> 4508f02e6cd7

ALTER TABLE cell ADD COLUMN modified DATETIME AFTER created;

UPDATE cell SET modified = NOW() WHERE modified IS NULL;

ALTER TABLE wifi ADD COLUMN modified DATETIME AFTER created;

UPDATE wifi SET modified = NOW() WHERE modified IS NULL;

UPDATE alembic_version SET version_num='4508f02e6cd7';
