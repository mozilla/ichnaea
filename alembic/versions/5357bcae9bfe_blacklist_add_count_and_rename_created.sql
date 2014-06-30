-- Running upgrade 383a10fbb4c8 -> 5357bcae9bfe

ALTER TABLE cell_blacklist CHANGE created time DATETIME NULL;

ALTER TABLE wifi_blacklist CHANGE created time DATETIME NULL;

ALTER TABLE cell_blacklist ADD COLUMN count INTEGER;

ALTER TABLE wifi_blacklist ADD COLUMN count INTEGER;

UPDATE cell_blacklist SET count = 1 WHERE count IS NULL;

UPDATE wifi_blacklist SET count = 1 WHERE count IS NULL;

UPDATE alembic_version SET version_num='5357bcae9bfe';
